import asyncio
import logging

import aio_pika
import msgpack

from consumer.storage.rabbit import channel_pool


async def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    queue_name = "test_queue"

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        # Will take no more than 10 messages in advance
        await channel.set_qos(prefetch_count=10)

        # Declaring queue
        queue = await channel.declare_queue(queue_name, durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    logging.error(message.body)
                    print(msgpack.unpackb(message.body))
