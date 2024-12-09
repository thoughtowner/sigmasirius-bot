import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from ..mappers.user_mapper import from_registration_data_to_user, from_registration_data_to_resident_additional_data, from_registration_data_to_role
from config.settings import settings
from storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from consumers.model.models import User, Role, ResidentAdditionalData, UserRole
from sqlalchemy.future import select
from sqlalchemy import insert


async def main() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting registration consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)
        registration_queue = await channel.declare_queue('registration_queue', durable=True)

        logger.info('Registration consumer started!')
        async with registration_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)
                    registration_data = msgpack.unpackb(message.body)
                    logger.info("Received message %s", registration_data)
                    user_instance = from_registration_data_to_user(registration_data)
                    resident_additional_data_instance = from_registration_data_to_resident_additional_data(registration_data)
                    role_instance = from_registration_data_to_role(registration_data)

                    try:
                        async with async_session() as db:
                            role_result = await db.execute(select(Role.id).filter(Role.title == role_instance.title))
                            role_id = role_result.scalar()

                            user_query = insert(User).values(
                                telegram_user_id=user_instance.telegram_user_id,
                                full_name=user_instance.full_name,
                                phone_number=user_instance.phone_number,
                            ).returning(User.id)

                            user_result = await db.execute(user_query)
                            user_id = user_result.scalar()

                            resident_additional_data_query = insert(ResidentAdditionalData).values(
                                room=resident_additional_data_instance.room,
                                user_id=user_id
                            )

                            await db.execute(resident_additional_data_query)

                            user_role_query = insert(UserRole).values(
                                user_id=user_id,
                                role_id=role_id,
                            )

                            await db.execute(user_role_query)
                            await db.commit()

                            async with channel_pool.acquire() as _channel:
                                registration_exchange = await _channel.get_exchange('registration_exchange')
                                user_registration_queue = await _channel.declare_queue(
                                    f'user_registration_queue.{registration_data["telegram_user_id"]}',
                                    durable=True
                                )
                                await user_registration_queue.bind(
                                    registration_exchange,
                                    f'user_registration_queue.{registration_data["telegram_user_id"]}'
                                )
                                await registration_exchange.publish(
                                    aio_pika.Message(msgpack.packb(True)),
                                    f'user_registration_queue.{registration_data["telegram_user_id"]}'
                                )
                    except IntegrityError:
                        logger.info("This user with this data is already registered: %s", registration_data)
                        async with channel_pool.acquire() as _channel:
                            registration_exchange = await _channel.declare_exchange("registration_exchange", ExchangeType.DIRECT, durable=True)
                            user_registration_queue = await _channel.declare_queue(
                                f'user_registration_queue.{registration_data["telegram_user_id"]}',
                                durable=True,
                            )
                            await user_registration_queue.bind(
                                registration_exchange,
                                settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(
                                    telegram_user_id=registration_data['telegram_user_id']
                                )
                            )
                            await registration_exchange.publish(
                                aio_pika.Message(msgpack.packb(False)),
                                settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(
                                    telegram_user_id=registration_data['telegram_user_id']
                                )
                            )
