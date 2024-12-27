import asyncio

import aio_pika
import msgpack
from aio_pika.exceptions import QueueEmpty
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aio_pika import Queue

from config.settings import settings
from src.storage.rabbit import channel_pool
from ..router import router

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

from src.logger import LOGGING_CONFIG, logger

from aio_pika import ExchangeType


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

@router.callback_query(lambda callback_query: callback_query.data == 'take_application_form_for_processing')
async def take_application_form_for_processing(callback_query: CallbackQuery, state: FSMContext) -> None:
    telegram_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    # state_data = await state.get_data()
    # if not 'application_form_ids_and_message_ids' in state_data:
    #     state_data['application_form_ids_and_message_ids'] = []
    # state_data['application_form_ids_and_message_ids'].append(
    #     {
    #         'application_form_id': ...,
    #         'message_ids': message_id
    #     }
    # )
    # await state.update_data(state_data)

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to application_form queue...')

        application_form_exchange = await channel.declare_exchange(settings.APPLICATION_FORM_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        application_form_queue = await channel.declare_queue(settings.APPLICATION_FORM_QUEUE_NAME, durable=True)
        await application_form_queue.bind(application_form_exchange, settings.APPLICATION_FORM_QUEUE_NAME)

        await application_form_exchange.publish(
            aio_pika.Message(
                msgpack.packb(
                    {
                        'event': 'change_application_form_status',
                        'action': 'take_application_form_for_processing',
                        'working_admin_telegram_id': telegram_id,
                        'working_admin_message_id': message_id,
                        'new_status': 'in_processing'
                    }
                ),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.APPLICATION_FORM_QUEUE_NAME
        )
