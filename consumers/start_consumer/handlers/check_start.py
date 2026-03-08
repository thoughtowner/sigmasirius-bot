from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm
from sqlalchemy import select, insert

from ..schema.check_start import CheckStartMessage

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

async def handle_check_start_event(message): # TODO async def handle_check_start_event(message: CheckStartMessage)
    async with async_session() as db:
        user_query = await db.execute(
            select(User).filter(User.telegram_id == message['telegram_id']))
        user = user_query.scalar()

        if user:
            flag = False
            logger.info('This user with this data is already start: %s', message)
        else:
            flag = True
            logger.info('This user with this data is not start: %s', message)

        async with channel_pool.acquire() as _channel:
            start_exchange = await _channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            reverse_start_queue = await _channel.declare_queue(
                settings.REVERSE_START_QUEUE_NAME,
                durable=True
            )
            await reverse_start_queue.bind(
                start_exchange,
                settings.REVERSE_START_QUEUE_NAME
            )
            await start_exchange.publish(
                aio_pika.Message(msgpack.packb({'flag': flag})),
                settings.REVERSE_START_QUEUE_NAME
            )
