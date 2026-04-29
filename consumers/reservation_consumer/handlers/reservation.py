from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm, Reservation, RoomClass
from sqlalchemy import insert, select

from ..schema import ReservationMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.msg_templates.env import render
from datetime import datetime


import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool
import uuid

import qrcode


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_reservation_event(message): # TODO async def handle_reservation_event(message: ReservationMessage)
    async with async_session() as db:
        user_result = await db.execute(
            select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

        await db.execute(insert(Reservation).values(
            id=uuid.UUID(message['reservation_id']),
            people_quantity=int(message['people_quantity']),
            room_class=RoomClass(message['room_class']),
            check_in_date=datetime.strptime(message['check_in_date'], '%Y-%m-%d').date(),
            eviction_date=datetime.strptime(message['eviction_date'], '%Y-%m-%d').date(),
            user_id=user_id
        ))

        await db.commit()

        if not message['is_test_data']:
            buf = io.BytesIO()
            img = qrcode.make('reservation/' + message['reservation_id'])
            img.save(buf, format='PNG')
            buf.seek(0)

            # store generated QR in object storage (MinIO)
            try:
                images_storage.upload_file(f"reservation/{message['reservation_id']}.png", io.BytesIO(buf.getvalue()))
            except Exception:
                logger.exception('Failed to upload reservation QR to storage')

            image_file = BufferedInputFile(file=buf.read(), filename='reservation_qr.png')
            # prepare reservation text
            res_text = (
                f"ID: {message['reservation_id']}\n"
                f"Гостей: {message['people_quantity']}\n"
                f"Класс: {message['room_class']}\n"
                f"Заезд: {message['check_in_date']}\n"
                f"Выезд: {message['eviction_date']}\n"
            )

            # import bot lazily to avoid circular import at module import time
            from src.bot import bot
            # include an inline cancel button that the bot will handle
            try:
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data=f'cancel_by_id:{message["reservation_id"]}')]])
            except Exception:
                kb = None

            sent_msg = await bot.send_photo(
                chat_id=message['telegram_id'], photo=image_file,
                caption='Ваш QR-код для заселения. Покажите его на ресепшене.\n\n' + res_text,
                reply_markup=kb
            )

            # store mapping in redis so we can later remove inline markup for old reservations
            try:
                from src.storage.redis import redis_storage
                import json
                member = {'telegram_id': message['telegram_id'], 'message_id': sent_msg.message_id}
                key = f'reservation:{str(message["reservation_id"])}:members'
                current_raw = await redis_storage.get(key)
                if current_raw:
                    try:
                        current = json.loads(current_raw)
                    except Exception:
                        current = []
                else:
                    current = []
                current.append(member)
                await redis_storage.set(key, json.dumps(current))
                # reverse lookup
                await redis_storage.set(f'reservation_message_map:{message["telegram_id"]}:{sent_msg.message_id}', str(message['reservation_id']))
            except Exception:
                logger.exception('Failed to write reservation mapping into redis')

    # send start keyboard but do not clear reservation markups here
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(message.get('telegram_id'), clear_reservation_markups=False)
    except Exception:
        pass

    # Do not send start keyboard here — it would remove the cancel button immediately.
    # The start keyboard (which also clears stale reservation markups) should be
    # invoked only when the user executes a new command.
