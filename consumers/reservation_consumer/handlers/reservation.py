from ..mappers import get_user, get_resident
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm, Resident
from sqlalchemy import insert, select

from ..schema import ReservationMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_reservation_event(message): # TODO async def handle_reservation_event(message: ReservationMessage)
    async with async_session() as db:
        user_result = await db.execute(
            select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

        # update user's phone and create resident record
        await db.execute(
            User.__table__.update().where(User.id == user_id).values(phone_number=message['phone_number'])
        )

        await db.execute(insert(Resident).values(
            full_name=message['full_name'],
            room=message['room'],
            user_id=user_id
        ))

        await db.commit()

        await bot.send_message(
            text='Вы успешно зарегистрировались!',
            chat_id=message['telegram_id']
        )
