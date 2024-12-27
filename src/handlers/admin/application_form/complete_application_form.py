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

@router.callback_query(lambda callback_query: callback_query.data == 'complete_application_form')
async def complete_application_form(callback_query: CallbackQuery, state: FSMContext) -> None:
    telegram_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    # state_data = await state.get_data()
    # for i, application_form_id_and_message_ids in enumerate(state_data['application_form_ids_and_message_ids']):
    #     if state_application_form_data['clicked_admin_data']['chat_id'] == telegram_id and state_application_form_data['clicked_admin_data']['message_id'] == message_id:
    #         del state_application_forms_data['application_form'][i]
    #         break
    # await state.update_data(application_forms_data=state_application_forms_data)

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
                        'action': 'complete_application_form',
                        'working_admin_telegram_id': telegram_id,
                        'working_admin_message_id': message_id,
                        'new_status': 'completed'
                    }
                ),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.APPLICATION_FORM_QUEUE_NAME
        )
