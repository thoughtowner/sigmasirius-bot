from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context
from consumers.registration_consumer.logger import correlation_id_ctx

from config.settings import settings
from src.schema.registration.registration import RegistrationMessage
from src.schema.registration.check_registration import CheckRegistrationMessage
from src.states.registration import Registration
from ..router import router
from src.keyboard_buttons.registration import BUILDINGS_ROW_BUTTONS, ENTRANCES_ROW_BUTTONS, FLOORS_ROW_BUTTONS, ROOM_NUMBERS_BY_FLOOR_ROW_BUTTONS
from aiogram.types import ReplyKeyboardRemove
from src.validators.registration.validators import FullNameValidator, PhoneNumberValidator
from src.validators.registration import errors as validation
from src.messages import registration as msg
from src.keyboard_buttons.texts import BUILDINGS, ENTRANCES, ROOM_NUMBERS_BY_FLOOR
from src.commands import REGISTRATION
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == REGISTRATION)
async def start_registration(message: Message, state: FSMContext):
    await state.update_data(telegram_id=message.from_user.id)
    await state.update_data(role='resident')

    data = await state.get_data()
    check_registration_message = CheckRegistrationMessage(
        event='check_registration',
        telegram_id=data['telegram_id'],
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to registration queue for check registration status...')
        registration_exchange = await channel.declare_exchange(settings.REGISTRATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        registration_queue = await channel.declare_queue(settings.REGISTRATION_QUEUE_NAME, durable=True)
        await registration_queue.bind(registration_exchange, settings.REGISTRATION_QUEUE_NAME)

        await registration_exchange.publish(
            aio_pika.Message(
                msgpack.packb(check_registration_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.REGISTRATION_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        user_registration_queue = await channel.declare_queue(
            settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(telegram_id=message.from_user.id),
            durable=True,
        )

        retries = 3
        for _ in range(retries):
            try:
                registration_response_message = await user_registration_queue.get()
                registration_flag = msgpack.unpackb(registration_response_message.body)
                break
            except QueueEmpty:
                await asyncio.sleep(1)

        if not registration_flag['flag']:
            await message.answer(msg.ALREADY_REGISTER)
            return

    await state.set_state(Registration.full_name)
    await message.answer(msg.ENTER_FULL_NAME)

@router.message(Registration.full_name)
async def enter_full_name(message: Message, state: FSMContext):
    answer = msg.ENTER_PHONE_NUMBER
    try:
        full_name = FullNameValidator().validate(message)
        await state.update_data(full_name=full_name)
        await state.set_state(Registration.phone_number)
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

@router.message(Registration.phone_number)
async def enter_phone_number(message: Message, state: FSMContext):
    answer = msg.CHOOSE_BUILDING
    reply_markup=None
    try:
        phone_number = PhoneNumberValidator().validate(message)
        await state.update_data(phone_number=phone_number)
        await state.set_state(Registration.building)
        reply_markup = BUILDINGS_ROW_BUTTONS
    except validation.InvalidPhoneNumberFormatError:
        answer = msg.INVALID_PHONE_NUMBER_FORMAT
    finally:
        await message.answer(answer, reply_markup=reply_markup)

@router.message(Registration.building)
async def enter_building(message: Message, state: FSMContext):
    building = message.text
    if building not in BUILDINGS:
        await message.answer(msg.INVALID_BUILDING)
        return
    await state.update_data(building=building)
    await state.set_state(Registration.entrance)
    await message.answer(msg.CHOOSE_ENTRANCE, reply_markup=ENTRANCES_ROW_BUTTONS)

@router.message(Registration.entrance)
async def enter_entrance(message: Message, state: FSMContext):
    entrance = message.text
    if entrance not in ENTRANCES:
        await message.answer(msg.INVALID_ENTRANCE)
        return
    await state.update_data(entrance=entrance)
    await state.set_state(Registration.floor)
    await message.answer(msg.CHOOSE_FLOOR, reply_markup=FLOORS_ROW_BUTTONS)

@router.message(Registration.floor)
async def enter_floor(message: Message, state: FSMContext):
    floor = message.text
    if floor not in ROOM_NUMBERS_BY_FLOOR.keys():
        await message.answer(msg.INVALID_FLOOR)
        return
    await state.update_data(floor=floor)
    await state.set_state(Registration.room_number)
    await message.answer(msg.CHOOSE_ROOM_NUMBER, reply_markup=ROOM_NUMBERS_BY_FLOOR_ROW_BUTTONS[floor])

@router.message(Registration.room_number)
async def enter_room_number(message: Message, state: FSMContext):
    room_number = message.text
    data_without_room_number = await state.get_data()
    floor = data_without_room_number.get('floor')
    if room_number not in ROOM_NUMBERS_BY_FLOOR[floor]:
        await message.answer(msg.INVALID_ROOM_NUMBER)
        return
    await state.update_data(room_number=room_number)
    data = await state.get_data()
    await message.answer(msg.PUSH_DATA_TO_REGISTRATION_QUERY, reply_markup=ReplyKeyboardRemove())

    await state.set_state('')
    # await state.clear()

    registration_message = RegistrationMessage(
        event='registration',
        telegram_id=data['telegram_id'],
        full_name=data['full_name'],
        phone_number=data['phone_number'],
        room=f"0{data['building']}-0{data['entrance']}-{data['room_number']}"
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to registration queue...')
        registration_exchange = await channel.declare_exchange(settings.REGISTRATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        registration_queue = await channel.declare_queue(settings.REGISTRATION_QUEUE_NAME, durable=True)
        await registration_queue.bind(registration_exchange, settings.REGISTRATION_QUEUE_NAME)

        await registration_exchange.publish(
            aio_pika.Message(
                msgpack.packb(registration_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.REGISTRATION_QUEUE_NAME
        )
