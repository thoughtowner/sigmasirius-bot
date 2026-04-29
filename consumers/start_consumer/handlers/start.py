from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, Reservation, ReservationStatus
from sqlalchemy import select, insert

from ..schema.start import StartMessage

from src.msg_templates.env import render

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool



async def handle_start_event(message):
    async with async_session() as db:
        existing_user_query = await db.execute(
            select(User).filter(User.telegram_id == message['telegram_id'])
        )
        existing_user = existing_user_query.scalar_one_or_none()

        if not existing_user:
            user_query = insert(User).values(
                telegram_id=message['telegram_id'],
                full_name=message['full_name'],
                phone_number=message['phone_number'],
            )
            await db.execute(user_query)
            await db.commit()
            
            # if not message['is_test_data']:
            #     await bot.send_message(
            #         text='Добро пожаловать!',
            #         chat_id=message['telegram_id']
            #     )

        user_query = await db.execute(
            select(User).filter(User.telegram_id == message['telegram_id'])
        )
        user = user_query.scalar_one()

        reservation_query = await db.execute(
            select(Reservation).filter(Reservation.user_id == user.id)
        )
        reservations = reservation_query.scalars().all()

        has_awaiting = any(r.status == ReservationStatus.UNCONFIRM for r in reservations)
        has_in_progress = any(r.status == ReservationStatus.IN_PROGRESS for r in reservations)

        if not message['is_test_data']:
            # Admin / repairman: keep informational text only
            if user.is_admin:
                await bot.send_message(
                    text=render('start/start_for_admin.jinja2'),
                    chat_id=message['telegram_id']
                )

            elif user.is_repairman:
                await bot.send_message(
                    text=render('start/start_for_repairman.jinja2'),
                    chat_id=message['telegram_id']
                )

            else:
                # For residents: delegate to the shared helper to build and send the start keyboard
                try:
                    await send_reply_start_keyboard(message['telegram_id'])
                except Exception:
                    logger.exception('Failed to send start keyboard via send_reply_start_keyboard')


async def send_reply_start_keyboard(telegram_id: int, clear_reservation_markups: bool = True):
    """Send a reply-keyboard with main bot commands (used when user cancels flows).
    This is a lightweight helper to avoid invoking full handle_start_event and
    avoid circular imports.
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    # Build keyboard based on user state in DB
    try:
        async with async_session() as db:
            q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
            user = q.scalar_one_or_none()

            # If user not registered yet -> show only /start
            if not user:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='/start', callback_data='start_cmd:start')],
                ])
                try:
                    await bot.send_message(chat_id=telegram_id, text='Выберите действие:', reply_markup=kb)
                except Exception:
                    logger.exception('Failed to send start-only keyboard')
                # still attempt to clear reservation markups below if requested
            else:
                # Admins and repairmen do not receive informational message
                if user.is_admin or user.is_repairman:
                    return

                # Resident: build keyboard depending on reservation status
                reservation_query = await db.execute(
                    select(Reservation).filter(Reservation.user_id == user.id)
                )
                reservations = reservation_query.scalars().all()
                has_any = bool(reservations)
                has_in_progress = any(r.status == ReservationStatus.IN_PROGRESS for r in reservations)

                kb_rows = []
                kb_rows.append([InlineKeyboardButton(text='/create_reservation', callback_data='start_cmd:create_reservation')])

                if not has_any:
                    kb_rows.append([InlineKeyboardButton(text='/become_repairman', callback_data='start_cmd:become_repairman')])
                else:
                    kb_rows.append([InlineKeyboardButton(text='/check_my_reservation', callback_data='start_cmd:check_my_reservation')])
                    kb_rows.append([InlineKeyboardButton(text='/check_my_reservations_archive', callback_data='start_cmd:check_my_reservations_archive')])
                    if has_in_progress:
                        kb_rows.append([InlineKeyboardButton(text='/add_application_form', callback_data='start_cmd:add_application_form')])

                kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                try:
                    await bot.send_message(chat_id=telegram_id, text='Выберите действие:', reply_markup=kb)
                except Exception:
                    logger.exception('Failed to send reply start keyboard')

    except Exception:
        # If DB check fails, fall back to the generic keyboard
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='/create_reservation', callback_data='start_cmd:create_reservation')],
                [InlineKeyboardButton(text='/check_my_reservation', callback_data='start_cmd:check_my_reservation')],
                [InlineKeyboardButton(text='/check_my_reservations_archive', callback_data='start_cmd:check_my_reservations_archive')],
                [InlineKeyboardButton(text='/add_application_form', callback_data='start_cmd:add_application_form')],
            ])
            await bot.send_message(chat_id=telegram_id, text='Выберите действие:', reply_markup=kb)
        except Exception:
            logger.exception('Failed to send fallback start keyboard')

    if not clear_reservation_markups:
        return

    # Clear old reservation inline markups so user cannot interact with stale reservation messages
    try:
        from src.storage.redis import redis_storage
        keys = await redis_storage.keys(f'reservation_message_map:{telegram_id}:*')
        if keys:
            for k in keys:
                try:
                    # key format: reservation_message_map:{telegram_id}:{message_id}
                    parts = k.split(b':') if isinstance(k, (bytes, bytearray)) else k.split(':')
                    message_id = int(parts[-1])
                    try:
                        await bot.edit_message_reply_markup(chat_id=telegram_id, message_id=message_id, reply_markup=None)
                    except Exception:
                        pass
                    try:
                        await redis_storage.delete(k)
                    except Exception:
                        pass
                except Exception:
                    logger.exception('Failed to clear reservation markup for key %s', k)
    except Exception:
        logger.exception('Failed to scan reservation_message_map keys')


async def clear_reservation_markups(telegram_id: int):
    """Clear inline 'Отменить' buttons for reservations for given telegram_id.
    Separated helper so callers can clear without sending the start keyboard.
    """
    try:
        from src.storage.redis import redis_storage
        keys = await redis_storage.keys(f'reservation_message_map:{telegram_id}:*')
        if keys:
            for k in keys:
                try:
                    parts = k.split(b':') if isinstance(k, (bytes, bytearray)) else k.split(':')
                    message_id_raw = parts[-1]
                    if isinstance(message_id_raw, (bytes, bytearray)):
                        message_id = int(message_id_raw.decode('utf-8'))
                    else:
                        message_id = int(message_id_raw)
                    try:
                        await bot.edit_message_reply_markup(chat_id=telegram_id, message_id=message_id, reply_markup=None)
                    except Exception:
                        pass
                    try:
                        await redis_storage.delete(k)
                    except Exception:
                        pass
                except Exception:
                    logger.exception('Failed to clear reservation markup for key %s', k)
    except Exception:
        logger.exception('Failed to scan reservation_message_map keys')
