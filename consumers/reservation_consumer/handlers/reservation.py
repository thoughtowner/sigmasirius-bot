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

from consumers.start_consumer.handlers.start import handle_start_event

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
            # import bot lazily to avoid circular import at module import time
            from src.bot import bot
            await bot.send_photo(
                chat_id=message['telegram_id'], photo=image_file,
                caption='Ваш QR-код для заселения. Покажите его на ресепшене.',
            )

    await handle_start_event(message=message)
