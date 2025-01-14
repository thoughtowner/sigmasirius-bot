import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from .handlers.add_application_form import handle_add_application_form_event
from .handlers.change_application_form_status import handle_change_application_form_status_event

from .metrics import TOTAL_RECEIVED_MESSAGES


async def application_form_consumer() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting application_form consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        application_form_queue = await channel.declare_queue('application_form_queue', durable=True)

        logger.info('Application_form consumer started!')
        async with application_form_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                TOTAL_RECEIVED_MESSAGES.inc()
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)

                    body = msgpack.unpackb(message.body)
                    logger.info("Received message %s", body)

                    if body['event'] == 'add_application_form':
                        await handle_add_application_form_event(body)
                    elif body['event'] == 'change_application_form_status':
                        await handle_change_application_form_status_event(body)
