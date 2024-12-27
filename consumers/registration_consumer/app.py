import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from .mappers import get_user, get_resident_additional_data, get_admin_additional_data
from config.settings import settings
from storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from .model.models import User, Role, ResidentAdditionalData, UserRole
from sqlalchemy import select, insert, and_

from .metrics import TOTAL_RECEIVED_MESSAGES

from .handlers.check_registration import handle_check_registration_event
from .handlers.registration import handle_registration_event


async def registration_consumer() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting registration consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        registration_queue = await channel.declare_queue(settings.REGISTRATION_QUEUE_NAME, durable=True)

        logger.info('Registration consumer started!')
        async with registration_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                TOTAL_RECEIVED_MESSAGES.inc()
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)

                    body = msgpack.unpackb(message.body)
                    logger.info("Received message %s", body)

                    if body['event'] == 'check_registration':
                        await handle_check_registration_event(body)
                    elif body['event'] == 'registration':
                        await handle_registration_event(body)
