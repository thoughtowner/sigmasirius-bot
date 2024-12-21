import asyncio

import aio_pika
import msgpack
from aio_pika.exceptions import QueueEmpty
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aio_pika import Queue

from config.settings import settings
from src.storage.rabbit import channel_pool
from .router import router

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

@router.callback_query(lambda callback_query: callback_query.data == 'cancel')
async def cancel(callback_query: CallbackQuery, state: FSMContext) -> None:
    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        application_form_for_admins_queue = await channel.declare_queue('application_form_for_admins_queue', durable=True)

        retries = 3
        for _ in range(retries):
            try:
                packed_application_form_for_admins_response_message = await application_form_for_admins_queue.get(no_ack=True)
                application_form_for_admins_response_message = msgpack.unpackb(packed_application_form_for_admins_response_message.body)

                application_form_for_admins_data = application_form_for_admins_response_message['application_form_for_user_data']['admins']
                application_form_for_owner_data = application_form_for_admins_response_message['application_form_for_user_data']['owner']
                caption = application_form_for_admins_response_message['caption']
                caption['status'] = 'cancelled'

                for application_form_for_admin_data in application_form_for_admins_data:
                    await bot.delete_message(chat_id=application_form_for_admin_data['chat_id'], message_id=application_form_for_admin_data['message_id'])

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=caption
                    ),
                    chat_id=application_form_for_owner_data['chat_id'],
                    message_id=application_form_for_owner_data['message_id']
                )

                return
            except QueueEmpty:
                await asyncio.sleep(1)

    await callback_query.message.answer('Что-то пошло не так')
