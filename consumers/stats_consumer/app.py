import logging.config

import aio_pika
import msgpack

from .logger import LOGGING_CONFIG, logger
from .storage.rabbit import channel_pool

from config.settings import settings
from .storage.db import async_session

from aio_pika import ExchangeType

from .handlers.stats import handle_admin_stats_event, handle_repairman_stats_event

from .metrics import TOTAL_RECEIVED_MESSAGES


async def stats_consumer() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting stats consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        stats_queue = await channel.declare_queue(settings.STATS_QUEUE_NAME, durable=True)

        logger.info('Stats consumer started!')
        async with stats_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                TOTAL_RECEIVED_MESSAGES.inc()
                async with message.process():
                    body = msgpack.unpackb(message.body)
                    logger.info("Received message %s", body)

                    if body.get('event') == 'admin_stats':
                        await handle_admin_stats_event(body)
                    elif body.get('event') == 'repairman_stats':
                        await handle_repairman_stats_event(body)
