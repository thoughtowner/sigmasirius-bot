import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from ..mappers.user_mapper import from_registration_data_to_user, from_registration_data_to_resident_additional_data, from_registration_data_to_role
from config.settings import settings
from src.storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError


async def main() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting registration consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        queue = await channel.declare_queue(settings.REGISTRATION_QUEUE_NAME, durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)
                    registration_data = msgpack.unpackb(message.body)
                    logger.info("Received message %s", registration_data)
                    user = from_registration_data_to_user(registration_data)
                    resident_additional_data = from_registration_data_to_resident_additional_data(registration_data)
                    role = from_registration_data_to_role(registration_data)

                    _queue_name = settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(user_id=registration_data['user_id'])

                    try:
                        async with async_session() as db:
                            db.add(user)
                            db.add(resident_additional_data)
                            db.add(role)
                            await db.commit()

                            async with channel_pool.acquire() as _channel:
                                _exchange = await _channel.declare_exchange("registration_exchange", ExchangeType.DIRECT, durable=True)
                                _queue = await channel.declare_queue(_queue_name, durable=True)
                                await _queue.bind(_exchange, '1')
                                await _exchange.publish(aio_pika.Message(msgpack.packb(True)), '1')
                    except IntegrityError:
                        logger.info("This user with this data is already registered: %s", registration_data)
                        async with channel_pool.acquire() as _channel:
                            _exchange = await _channel.declare_exchange("registration_exchange", ExchangeType.DIRECT, durable=True)
                            _queue = await channel.declare_queue(_queue_name, durable=True)
                            await _queue.bind(_exchange, '1')
                            await _exchange.publish(aio_pika.Message(msgpack.packb(False)), '1')
