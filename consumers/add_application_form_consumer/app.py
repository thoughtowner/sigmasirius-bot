import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from ..mappers import from_application_form_data_to_user, from_application_form_data_to_application_form
from config.settings import settings
from storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from consumers.model.models import User, ApplicationForm
from sqlalchemy import insert, select


async def main() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting add_application_form consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        add_application_form_queue = await channel.declare_queue('add_application_form_queue', durable=True)

        logger.info('Add_application_form consumer started!')
        async with add_application_form_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)
                    application_form_data = msgpack.unpackb(message.body)
                    logger.info("Received message %s", application_form_data)
                    user_instance = from_application_form_data_to_user(application_form_data)
                    application_form_instance = await from_application_form_data_to_application_form(application_form_data)

                    try:
                        async with async_session() as db:
                            user_result = await db.execute(select(User.id).filter(User.telegram_user_id == user_instance.telegram_user_id))
                            user_id = user_result.scalar()

                            application_form_query = insert(ApplicationForm).values(
                                title=application_form_instance.title,
                                description=application_form_instance.description,
                                photo=application_form_instance.photo,
                                status_id=application_form_instance.status_id,
                                user_id=user_id
                            )

                            await db.execute(application_form_query)
                            await db.commit()

                            # Отправить ответное сообщение из консюмера напрямую в бота TODO
                    except IntegrityError:
                        pass
                        # Отправить ответное сообщение из консюмера напрямую в бота TODO
