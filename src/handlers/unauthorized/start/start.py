from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context

from src.states.start import Start
from config.settings import settings
from src.schema.start.start import StartMessage
from src.schema.start.check_start import CheckStartMessage
from src.schema.start.check_phone_number import CheckPhoneNumberMessage
from ..router import router
from src.messages import start as msg
from src.commands import START
from src.validators.start.validators import PhoneNumberValidator, FullNameValidator
from src.validators.start import errors as validation
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == START)
async def check_start(message: Message, state: FSMContext):
    await state.update_data(telegram_id=message.from_user.id)

    data = await state.get_data()
    check_start_message = CheckStartMessage(
        event='check_start',
        telegram_id=data['telegram_id'],
        is_test_data=False,
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to start queue for check start status...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(check_start_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.START_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        reverse_start_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(
                telegram_id=message.from_user.id
            ),
            durable=True,
        )

        retries = 10
        for _ in range(retries):
            try:
                start_response_message = await reverse_start_queue.get(no_ack=True)
                body = msgpack.unpackb(start_response_message.body)
                break
            except QueueEmpty:
                await asyncio.sleep(1)

        # if not body:
        #     state_data = await state.get_data()
        #     await state.clear()
        #     await state.update_data(state_data)
        #     return
        await state.update_data(flag=body['flag'])
        if body['flag']:
            await state.set_state(Start.full_name)
            await message.answer(msg.ENTER_FULL_NAME)
        else:
            await message.answer(msg.WELCOME_BACK)

            state_data = await state.get_data()
            await state.clear()
            await state.update_data(state_data)

            start_message = StartMessage(
                event='start',
                telegram_id=state_data['telegram_id'],
                full_name="null",
                phone_number="null",
                # flag=state_data['flag']
                is_test_data=False,
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

@router.message(Start.full_name)
async def enter_full_name(message: Message, state: FSMContext):
    answer = msg.ENTER_PHONE_NUMBER
    try:
        full_name = FullNameValidator().validate(message)
        await state.update_data(full_name=full_name)
        await state.set_state(Start.phone_number)
    except validation.FullNameCannotContainMultipleSpacesError:
        answer = msg.FULL_NAME_CANNOT_CONTAIN_MULTIPLE_SPACES
    except validation.InvalidFullNameFormatError:
        answer = msg.INVALID_FULL_NAME_FORMAT
    except validation.NameShouldContainOnlyLettersError:
        answer = msg.NAME_SHOULD_CONTAIN_ONLY_LETTERS
    except validation.TooLongNameError:
        answer = msg.TOO_LONG_NAME
    except validation.TooShortNameError:
        answer = msg.TOO_SHORT_NAME
    except validation.NameBeginCannotBeLowercaseError:
        answer = msg.NAME_BEGIN_CANNOT_BE_LOWER
    finally:
        await message.answer(answer)

@router.message(Start.phone_number)
async def enter_phone_number(message: Message, state: FSMContext):
    try:
        phone_number = PhoneNumberValidator().validate(message)
        await state.update_data(phone_number=phone_number)
    except validation.InvalidPhoneNumberFormatError:
        await message.answer(msg.INVALID_PHONE_NUMBER_FORMAT)
        return
    
    data = await state.get_data()
    check_phone_number_message = CheckPhoneNumberMessage(
        event='check_phone_number',
        telegram_id=data['telegram_id'],
        is_test_data=False,
        phone_number=phone_number
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to start queue for check phone number status...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(check_phone_number_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.START_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        reverse_start_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(
                telegram_id=message.from_user.id
            ),
            durable=True,
        )

        retries = 10
        for _ in range(retries):
            try:
                check_phone_response_message = await reverse_start_queue.get(no_ack=True)
                body = msgpack.unpackb(check_phone_response_message.body)
                break
            except QueueEmpty:
                await asyncio.sleep(1)

        # if not body:
        #     state_data = await state.get_data()
        #     await state.clear()
        #     await state.update_data(state_data)
        #     return
        await state.update_data(flag=body['flag'])
        if not body['flag']:
            await message.answer('Этот номер телефона уже используется другим пользователем!')
            return
    
    state_data = await state.get_data()
    await state.clear()
    await state.update_data(state_data)

    start_message = StartMessage(
        event='start',
        telegram_id=state_data['telegram_id'],
        full_name=state_data['full_name'],
        phone_number=state_data['phone_number'],
        # flag=state_data['flag']
        is_test_data=False,
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
