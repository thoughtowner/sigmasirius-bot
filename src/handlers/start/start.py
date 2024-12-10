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
from consumers.start_consumer.schema.start_data import StartData
from src.states.start import Start
from .router import router
from src.messages import start as msg
from src.commands import START
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == START)
async def start(message: Message, state: FSMContext):
    await state.update_data(telegram_user_id=message.from_user.id)
    data = await state.get_data()

    start_data = StartData(
        telegram_user_id=data['telegram_user_id']
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to start queue...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(start_data),
                # correlation_id=correlation_id_ctx.get()
                # correlation_id=context.get(HeaderKeys.correlation_id)
            ),
            settings.START_QUEUE_NAME
        )

    # Получаем ответное сообщение из консюмера не используя очередь пользователя TODO

    await state.set_state(Start.info)
    await message.answer(msg.INFO)
    await message.answer('/registration')
    await message.answer('/add_application_form')
    await message.answer('/listening_application_forms')
    await state.clear()
