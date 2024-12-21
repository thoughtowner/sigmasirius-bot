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


# async def listen(callback_query: CallbackQuery, user_id: str):
#     async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
#         queue: Queue = await channel.declare_queue(settings.USER_GIFT_QUEUE_TEMPLATE.format(user_id=user_id), durable=True)
#         message = await queue.get()
#         parsed_message: Gift = msgpack.unpackb(message)
#         await callback_query.answer(parsed_message)

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

@router.callback_query()
async def take_for_processing(callback_query: CallbackQuery, state: FSMContext) -> None:
    telegram_user_id = callback_query.from_user.id

    # user_data_per_callback = user_data[callback_query.data]

    # await callback_query.message.delete_reply_markup()

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        application_form_for_admins_queue = await channel.declare_queue('application_form_for_admins_queue', durable=True)

        retries = 3
        for _ in range(retries):
            try:
                packed_application_form_for_admins_response_message = await application_form_for_admins_queue.get(no_ack=True)
                application_form_for_admins_response_message = msgpack.unpackb(packed_application_form_for_admins_response_message.body)

                # async with aiohttp.ClientSession() as session:
                #     async with session.get('https://cdn.velostrana.ru/upload/models/velo/63352/full.jpg') as response:
                #         content = await response.read()
                #
                # photo = BufferedInputFile(content, 'test')
                # # callback buttons

                application_form_for_admins_data = application_form_for_admins_response_message['application_form_for_admins_data']
                caption = application_form_for_admins_response_message['caption']
                for application_form_for_admin_data in application_form_for_admins_data:
                    if application_form_for_admin_data['chat_id'] == telegram_user_id:
                        caption['status'] = 'in_processing'

                        await bot.edit_message_caption(
                            caption=render(
                                'application_form_for_admins/application_form_for_admins.jinja2',
                                application_form_for_admins=caption
                            ),
                            chat_id=application_form_for_admin_data['chat_id'],
                            message_id=application_form_for_admin_data['message_id']
                        )

                        complete_btn = InlineKeyboardButton(text='Выполнить', callback_data='complete')
                        markup = InlineKeyboardMarkup(
                            inline_keyboard=[[complete_btn]]
                        )

                        await bot.edit_message_reply_markup(
                            chat_id=application_form_for_admin_data['chat_id'],
                            message_id=application_form_for_admin_data['message_id'],
                            reply_markup=markup
                        )
                    else:
                        await bot.delete_message(chat_id=application_form_for_admin_data['chat_id'], message_id=application_form_for_admin_data['message_id'])

                # inline_btn_1 = InlineKeyboardButton(text='Следующий подарок', callback_data='next_gift')
                # markup = InlineKeyboardMarkup(
                #     inline_keyboard=[[inline_btn_1]]
                # )
                #
                # await callback_query.message.answer_photo(
                #     photo=parsed_gift['photo'],
                #     caption=render('gift/gift.jinja2', gift=parsed_gift),
                #     reply_markup=markup,
                # )

                return
            except QueueEmpty:
                await asyncio.sleep(1)

        await callback_query.message.answer('Нет подарков')
