from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, Role, ApplicationForm, ResidentAdditionalData, ApplicationFormStatus, UserRole
from sqlalchemy import insert, select, and_

from ..schema.check_registration import CheckRegistrationMessage

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

async def handle_check_registration_event(message): # TODO async def handle_check_registration_event(message: CheckRegistrationMessage)
    async with async_session() as db:
        user_id_query = await db.execute(
            select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_id_query.scalar()

        resident_role_id_query = await db.execute(
            select(Role.id).filter(Role.title == 'resident'))
        resident_role_id = resident_role_id_query.scalar()

        user_role_query = await db.execute(
            select(UserRole).where(and_(UserRole.user_id == user_id, UserRole.role_id == resident_role_id)))
        user_role_result = user_role_query.all()

        if user_role_result:
            flag = False
            logger.info('This user with this data is already registered: %s', message)
        else:
            flag = True
            logger.info('This user with this data is not registered: %s', message)

        async with channel_pool.acquire() as _channel:
            registration_exchange = await _channel.declare_exchange(settings.REGISTRATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            user_registration_queue = await _channel.declare_queue(
                settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                ),
                durable=True,
            )
            await user_registration_queue.bind(
                registration_exchange,
                settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                )
            )
            await registration_exchange.publish(
                aio_pika.Message(msgpack.packb({'flag': flag})),
                settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                )
            )
