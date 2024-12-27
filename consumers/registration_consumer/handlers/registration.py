from ..mappers import get_user, get_resident_additional_data
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, Role, ApplicationForm, ResidentAdditionalData, ApplicationFormStatus, UserRole
from sqlalchemy import insert, select, and_

from ..schema.registration import RegistrationMessage

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

async def handle_registration_event(message): # TODO async def handle_registration_event(message: RegistrationMessage)
    async with async_session() as db:
        user_result = await db.execute(
            select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

        resident_role_id_query = await db.execute(
            select(Role.id).filter(Role.title == 'resident'))
        resident_role_id = resident_role_id_query.scalar()

        await db.execute(insert(UserRole).values(
            user_id=user_id,
            role_id=resident_role_id
        ))

        await db.flush()

        await db.execute(insert(ResidentAdditionalData).values(
            full_name=message['full_name'],
            phone_number=message['phone_number'],
            room=message['room'],
            user_id=user_id
        ))

        await db.commit()

        await bot.send_message(
            text='Вы успешно зарегистрировались!',
            chat_id=message['telegram_id']
        )
