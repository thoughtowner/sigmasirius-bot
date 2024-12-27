import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from .mappers import get_user
from config.settings import settings
from storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from .model.models import User, Role, ResidentAdditionalData, UserRole
from sqlalchemy.future import select
from sqlalchemy import insert

from config.settings import settings

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

from consumers.start_consumer.handlers.start import handle_start_event

from .metrics import TOTAL_RECEIVED_MESSAGES


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def start_consumer() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting start consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)

        logger.info('Start consumer started!')
        async with start_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                TOTAL_RECEIVED_MESSAGES.inc()
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)

                    body = msgpack.unpackb(message.body)
                    logger.info("Received message %s", body)

                    if body['event'] == 'start':
                        await handle_start_event(body)
