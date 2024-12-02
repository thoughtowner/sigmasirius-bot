import logging.config

import aio_pika
import msgpack

from consumer.logger import LOGGING_CONFIG, logger, correlation_id_ctx
from consumer.storage.rabbit import channel_pool


async def main() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting consumer...')

    queue_name = "test_queue"

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        # Will take no more than 10 messages in advance
        await channel.set_qos(prefetch_count=10)

        # Declaring queue
        queue = await channel.declare_queue(queue_name, durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                async with message.process():
                    correlation_id_ctx.set(message.correlation_id)
                    logger.info("Message ...")

                    print(msgpack.unpackb(message.body))
