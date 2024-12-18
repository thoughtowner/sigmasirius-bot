from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context

from consumers.add_application_form_consumer.logger import correlation_id_ctx

from config.settings import settings
from consumers.add_application_form_consumer.schema.application_form_data import ApplicationFormData
from src.states.add_application_form import AddApplicationForm
from .router import router
from src.validators.add_application_form.validators import TitleValidator, DescriptionValidator
from src.validators.add_application_form import errors as validation
from src.messages import add_application_form as msg
from src.commands import ADD_APPLICATION_FORM
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == ADD_APPLICATION_FORM)
async def start_add_application_form(message: Message, state: FSMContext):
    await state.update_data(telegram_user_id=message.from_user.id)
    await state.set_state(AddApplicationForm.title)
    await message.answer(msg.ENTER_TITLE)

@router.message(AddApplicationForm.title)
async def enter_title(message: Message, state: FSMContext):
    answer = msg.ENTER_DESCRIPTION
    try:
        title = TitleValidator().validate(message)
        await state.update_data(title=title)
        await state.set_state(AddApplicationForm.description)
    except validation.TooLongTitleError:
        answer = msg.TOO_LONG_TITLE
    finally:
        await message.answer(answer)

@router.message(AddApplicationForm.description)
async def enter_description(message: Message, state: FSMContext):
    answer = msg.UPLOAD_PHOTO
    try:
        description = DescriptionValidator().validate(message)
        await state.update_data(description=description)
        await state.set_state(AddApplicationForm.photo)
    except validation.TooLongDescriptionError:
        answer = msg.TOO_LONG_DESCRIPTION
    finally:
        await message.answer(answer)

@router.message(AddApplicationForm.photo)
async def upload_photo(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo=message.photo[-1].file_id)
        data = await state.get_data()
        await message.answer(msg.PUSH_INTO_REGISTRATION_QUERY)
        await state.clear()

        application_form_data = ApplicationFormData(
            telegram_user_id=data['telegram_user_id'],
            title=data['title'],
            description=data['description'],
            photo=data['photo'],
            status='not_completed'
        )

        async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
            logger.info('Send data to add_application_form queue...')
            add_application_form_exchange = await channel.declare_exchange(settings.ADD_APPLICATION_FORM_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            add_application_form_queue = await channel.declare_queue(settings.ADD_APPLICATION_FORM_QUEUE_NAME, durable=True)
            await add_application_form_queue.bind(add_application_form_exchange, settings.ADD_APPLICATION_FORM_QUEUE_NAME)

            await add_application_form_exchange.publish(
                aio_pika.Message(
                    msgpack.packb(application_form_data),
                    # correlation_id=correlation_id_ctx.get()
                ),
                settings.ADD_APPLICATION_FORM_QUEUE_NAME
            )

        # Получаем ответное сообщение из консюмера не используя очередь пользователя TODO

        await message.answer('Заявка отправлена')
