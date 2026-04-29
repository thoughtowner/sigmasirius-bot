from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context
from consumers.repairman_consumer.logger import correlation_id_ctx

from config.settings import settings
from src.schema.repairman.repairman import RepairmanMessage
from ..router import router
from src.storage.db import async_session
from src.messages import repairman as msg
from src.commands import QUIT_AS_REPAIRMAN
from src.logger import LOGGING_CONFIG, logger
import logging.config
from src.msg_templates.env import render

from aio_pika.exceptions import QueueEmpty
import asyncio

import uuid
import io
import qrcode
from aiogram.types import BufferedInputFile
from src.keyboard_buttons.qr import main_keyboard


logging.config.dictConfig(LOGGING_CONFIG)


@router.message(F.text == QUIT_AS_REPAIRMAN)
async def start_quit_as_repairman(message: Message, state: FSMContext):
    await state.update_data(telegram_id=message.from_user.id)

    data = await state.get_data()

    repairman_message = RepairmanMessage(
        event='quit_as_repairman',
        telegram_id=data['telegram_id'],
        is_test_data=False
    )

    async with channel_pool.acquire() as channel:
        logger.info('Send data to repairman queue for check repairman status...')
        repairman_exchange = await channel.declare_exchange(settings.REPAIRMAN_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        repairman_queue = await channel.declare_queue(settings.REPAIRMAN_QUEUE_NAME, durable=True)
        await repairman_queue.bind(repairman_exchange, settings.REPAIRMAN_QUEUE_NAME)

        await repairman_exchange.publish(
            aio_pika.Message(
                msgpack.packb(repairman_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.REPAIRMAN_QUEUE_NAME
        )
    
    await message.answer(msg.INFO)
    
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)
