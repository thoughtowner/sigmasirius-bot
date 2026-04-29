import logging.config

import aio_pika
import msgpack

from .logger import LOGGING_CONFIG, logger, correlation_id_ctx
from .storage.rabbit import channel_pool

from .mappers import get_user
from config.settings import settings
from .storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from .model.models import User
from sqlalchemy.future import select
from sqlalchemy import insert

from config.settings import settings

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.msg_templates.env import render
import asyncio

from consumers.repairman_consumer.handlers.become_repairman import handle_become_repairman_event
from consumers.repairman_consumer.handlers.quit_as_repairman import handle_quit_as_repairman_event
# support assign_repairman events handled by start_consumer.handlers.assign_repairman
from consumers.start_consumer.handlers.assign_repairman import handle_assign_repairman_event

from .metrics import TOTAL_RECEIVED_MESSAGES


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def repairman_consumer() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting repairman consumer...')

    async with channel_pool.acquire() as channel:

        await channel.set_qos(prefetch_count=10)

        repairman_queue = await channel.declare_queue(settings.REPAIRMAN_QUEUE_NAME, durable=True)

        logger.info('Repairman consumer started!')
        try:
            async with repairman_queue.iterator() as queue_iter:
                async for message in queue_iter: # type: aio_pika.Message
                    TOTAL_RECEIVED_MESSAGES.inc()
                    try:
                        async with message.process():
                            # correlation_id_ctx.set(message.correlation_id)

                            body = msgpack.unpackb(message.body)
                            logger.info("Received message %s", body)

                            if body['event'] == 'become_repairman':
                                await handle_become_repairman_event(body)
                            elif body['event'] == 'quit_as_repairman':
                                await handle_quit_as_repairman_event(body)
                            elif body['event'] == 'assign_repairman':
                                await handle_assign_repairman_event(body)
                    except asyncio.CancelledError:
                        # shutdown in progress
                        raise
                    except Exception:
                        logger.exception('Error processing message')
        except asyncio.CancelledError:
            logger.info('Repairman consumer cancelled')
        except KeyboardInterrupt:
            logger.info('Repairman consumer interrupted by KeyboardInterrupt')
        except Exception:
            logger.exception('Repairman consumer failed')
        finally:
            try:
                await bot.close()
            except Exception:
                pass
