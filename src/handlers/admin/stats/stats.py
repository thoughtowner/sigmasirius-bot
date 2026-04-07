from aiogram.types import Message
from aiogram import F
import aio_pika
import msgpack
from aio_pika import ExchangeType
from src.storage.rabbit import channel_pool
from config.settings import settings
from ..router import router
from src.commands import ADMIN_STATS
from aio_pika.exceptions import QueueEmpty
import asyncio

@router.message(F.text == ADMIN_STATS)
async def admin_stats(message: Message):
    admin_id = message.from_user.id

    async with channel_pool.acquire() as channel:
        stats_exchange = await channel.declare_exchange(settings.STATS_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await stats_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'admin_stats',
                'telegram_id': admin_id,
            })),
            settings.STATS_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:
        user_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id),
            durable=True,
        )

        retries = 30
        body = None
        for _ in range(retries):
            try:
                msg = await user_queue.get(no_ack=True)
                body = msgpack.unpackb(msg.body)
                break
            except QueueEmpty:
                await asyncio.sleep(0.5)

    if not body:
        await message.answer('Ошибка: нет ответа от сервера, повторите позже')
        return

    # body expected to contain text
    await message.answer(body.get('text', 'Нет данных'))
