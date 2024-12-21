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

@router.callback_query(lambda callback_query: callback_query.data == 'complete')
async def complete(callback_query: CallbackQuery, state: FSMContext) -> None:
    telegram_user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    application_form_data = None

    state_application_forms_data = await state.get_data()
    for state_application_form_id, state_application_form_data in state_application_forms_data['application_forms_data'].items():
        if state_application_form_data['admin_data']['chat_id'] == telegram_user_id and state_application_form_data['admin_data']['message_id'] == message_id:
            application_form_data = state_application_form_data
            application_form_id = state_application_form_id
            break

    if application_form_data is None:
        await bot.send_message(text='Что-то пошло не так', chat_id=telegram_user_id)
        return

    caption = application_form_data['caption']
    caption['status'] = 'completed'

    await bot.edit_message_caption(
        caption=render(
            'application_form_for_admins/application_form_for_admins.jinja2',
            application_form_for_admins=caption
        ),
        chat_id=application_form_data['owner_data']['chat_id'],
        message_id=application_form_data['owner_data']['message_id']
    )

    await bot.delete_message(chat_id=application_form_data['admin_data']['chat_id'], message_id=application_form_data['admin_data']['message_id'])

    del state_application_forms_data['application_forms_data'][application_form_id]
    await state.update_data(application_forms_data=state_application_forms_data)
