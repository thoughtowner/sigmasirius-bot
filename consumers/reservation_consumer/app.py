import logging.config

import aio_pika
import msgpack

from .logger import LOGGING_CONFIG, logger, correlation_id_ctx
from .storage.rabbit import channel_pool

from .mappers import get_user, get_resident
from config.settings import settings
from .storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from .model.models import User, Resident
from sqlalchemy import select, insert

from .metrics import TOTAL_RECEIVED_MESSAGES

from .handlers.check_reservation import handle_check_reservation_event
from .handlers.reservation import handle_reservation_event


async def reservation_consumer() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting reservation consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        reservation_queue = await channel.declare_queue(settings.reservation_QUEUE_NAME, durable=True)

        logger.info('reservation consumer started!')
        async with reservation_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                TOTAL_RECEIVED_MESSAGES.inc()
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)

                    body = msgpack.unpackb(message.body)
                    logger.info("Received message %s", body)

                    if body['event'] == 'check_reservation':
                        await handle_check_reservation_event(body)
                    elif body['event'] == 'reservation':
                        await handle_reservation_event(body)
