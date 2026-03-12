from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, Reservation, ReservationStatus
from sqlalchemy import select, insert

from ..schema.start import StartMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

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
            
            await bot.send_message(
                text='Добро пожаловать!',
                chat_id=message['telegram_id']
            )

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
            if has_in_progress:
                await bot.send_message(
                    text=render('start/start_for_resident_with_active_reservation.jinja2'),
                    chat_id=message['telegram_id']
                )

            elif has_awaiting:
                await bot.send_message(
                    text=render('start/start_for_resident_with_reservation.jinja2'),
                    chat_id=message['telegram_id']
                )

            else:
                await bot.send_message(
                    text=render('start/start_for_resident_without_reservation.jinja2'),
                    chat_id=message['telegram_id']
                )
