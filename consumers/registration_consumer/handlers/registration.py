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
    user_instance = get_user(message)
    resident_additional_data_instance = get_resident_additional_data(message)

    try:
        async with async_session() as db:
            user_result = await db.execute(
                select(User.id).filter(User.telegram_id == user_instance.telegram_id))
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
                full_name=resident_additional_data_instance.full_name,
                phone_number=resident_additional_data_instance.phone_number,
                room=resident_additional_data_instance.room,
                user_id=user_id
            ))

            await db.commit()

            async with channel_pool.acquire() as _channel:
                registration_exchange = await _channel.get_exchange('registration_exchange')
                user_registration_queue = await _channel.declare_queue(
                    f'user_registration_queue.{message["telegram_id"]}',
                    durable=True
                )
                await user_registration_queue.bind(
                    registration_exchange,
                    f'user_registration_queue.{message["telegram_id"]}'
                )
                await registration_exchange.publish(
                    aio_pika.Message(msgpack.packb({'flag': True})),
                    f'user_registration_queue.{message["telegram_id"]}'
                )

    except IntegrityError as e:
        print(e)