import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from consumers.add_application_form_consumer.handlers.application_form import handle_application_form_event
from consumers.add_application_form_consumer.handlers.application_form_status import handle_application_form_status_event


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

                    body = msgpack.unpackb(message.body)
                    logger.info("Received message %s", body)

                    if body.get('event') == 'application_form':
                        await handle_application_form_event(body)
                    elif body.get('event') == 'application_form_status':
                        await handle_application_form_status_event(body)
