from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context

from config.settings import settings
from src.schema.start import StartMessage
from ..router import router
from src.messages import start as msg
from src.commands import START
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == START)
async def start(message: Message, state: FSMContext):
    state_data = await state.get_data()
    await state.clear()
    await state.update_data(state_data)

    await state.update_data(telegram_id=message.from_user.id)
    data = await state.get_data()

    start_message = StartMessage(
        event='start',
        telegram_id=data['telegram_id'],
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to start queue...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(start_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.START_QUEUE_NAME
        )
