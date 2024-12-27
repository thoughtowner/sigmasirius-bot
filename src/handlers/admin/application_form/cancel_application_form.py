import asyncio

import aio_pika
import msgpack
from aio_pika import ExchangeType
from aio_pika.exceptions import QueueEmpty
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config.settings import settings
from src.storage.rabbit import channel_pool
from ..router import router
from src.logger import logger

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

@router.callback_query(lambda callback_query: callback_query.data == 'cancel_application_form')
async def cancel_application_form(callback_query: CallbackQuery, state: FSMContext) -> None:
    telegram_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to application_form queue...')

        application_form_exchange = await channel.declare_exchange(settings.APPLICATION_FORM_EXCHANGE_NAME,
                                                                   ExchangeType.DIRECT, durable=True)
        application_form_queue = await channel.declare_queue(settings.APPLICATION_FORM_QUEUE_NAME, durable=True)
        await application_form_queue.bind(application_form_exchange, settings.APPLICATION_FORM_QUEUE_NAME)

        await application_form_exchange.publish(
            aio_pika.Message(
                msgpack.packb(
                    {
                        'event': 'change_application_form_status',
                        'action': 'cancel_application_form',
                        'working_admin_telegram_id': telegram_id,
                        'working_admin_message_id': message_id,
                        'new_status': 'cancelled'
                    }
                ),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.APPLICATION_FORM_QUEUE_NAME
        )
