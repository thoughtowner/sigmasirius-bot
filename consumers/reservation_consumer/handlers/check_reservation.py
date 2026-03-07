from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm, Resident
from sqlalchemy import select

from ..schema import CheckReservationMessage

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

async def handle_check_reservation_event(message): # TODO async def handle_check_reservation_event(message: CheckReservationMessage)
    async with async_session() as db:
        user_id_query = await db.execute(
            select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_id_query.scalar()

        resident_query = await db.execute(select(Resident).filter(Resident.user_id == user_id))
        resident = resident_query.scalar()

        if resident:
            flag = False
            logger.info('This user with this data is already create reservation: %s', message)
        else:
            flag = True
            logger.info('This user with this data is not create reservation: %s', message)

        async with channel_pool.acquire() as _channel:
            reservation_exchange = await _channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            user_reservation_queue = await _channel.declare_queue(
                settings.USER_RESERVATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                ),
                durable=True,
            )
            await user_reservation_queue.bind(
                reservation_exchange,
                settings.USER_RESERVATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                )
            )
            await reservation_exchange.publish(
                aio_pika.Message(msgpack.packb({'flag': flag})),
                settings.USER_RESERVATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                )
            )
