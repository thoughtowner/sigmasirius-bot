import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from ..mappers import from_start_data_to_user
from config.settings import settings
from storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from consumers.model.models import User, Role, ResidentAdditionalData, UserRole
from sqlalchemy.future import select
from sqlalchemy import insert

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def main() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting start consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        start_queue = await channel.declare_queue('start_queue', durable=True)

        logger.info('Start consumer started!')
        async with start_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)
                    start_data = msgpack.unpackb(message.body)
                    logger.info("Received message %s", start_data)
                    user_instance = from_start_data_to_user(start_data)

                    try:
                        async with async_session() as db:
                            user_query = insert(User).values(
                                telegram_user_id=user_instance.telegram_user_id
                            )

                            await db.execute(user_query)
                            await db.commit()

                            await bot.send_message(
                                text=render('start/start.jinja2'),
                                chat_id=user_instance.telegram_user_id
                            )
                    except IntegrityError:
                        await bot.send_message(
                            text=render('start/start.jinja2'),
                            chat_id=user_instance.telegram_user_id
                        )
