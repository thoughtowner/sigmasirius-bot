from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context

from config.settings import settings
from consumers.registration_consumer.schema.registration import RegistrationData
from ..states.registration import Registration
from .router import router
from src.keyboard_buttons.registration import STUDY_GROUPS_ROW_BUTTONS, BUILDINGS_ROW_BUTTONS, ENTRANCES_ROW_BUTTONS, FLOORS_ROW_BUTTONS, ROOMS_BY_FLOOR_ROW_BUTTONS
from aiogram.types import ReplyKeyboardRemove
from src.validators.validators import FullNameValidator, AgeValidator, PhoneNumberValidator
from src.validators import errors as validation
from src.messages import registration as msg
from src.keyboard_buttons.texts import STUDY_GROUPS, BUILDINGS, ENTRANCES, ROOMS_BY_FLOOR
from src.commands import REGISTRATION
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika import Queue
from aio_pika.exceptions import QueueEmpty
from typing import Any
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == REGISTRATION)
async def start_registration(message: Message, state: FSMContext):
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(Registration.full_name)
    await message.answer(msg.ENTER_FULL_NAME)

@router.message(Registration.full_name)
async def enter_full_name(message: Message, state: FSMContext):
    answer = msg.ENTER_AGE
    try:
        full_name = FullNameValidator().validate(message)
        await state.update_data(full_name=full_name)
        await state.set_state(Registration.age)
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

@router.message(Registration.age)
async def enter_age(message: Message, state: FSMContext):
    answer = msg.CHOOSE_STUDY_GROUP
    reply_markup=None
    try:
        age = AgeValidator().validate(message)
        await state.update_data(age=age)
        await state.set_state(Registration.study_group)
        reply_markup = STUDY_GROUPS_ROW_BUTTONS
    except validation.AgeShouldBePositiveNumberError:
        answer = msg.AGE_SHOULD_BE_POSITIVE_NUMBER
    except validation.AgeShouldBeNumberError:
        answer = msg.AGE_SHOULD_BE_NUMBER
    except validation.AgeTooOldError:
        answer = msg.AGE_TOO_OLD
    finally:
        await message.answer(answer, reply_markup=reply_markup)

@router.message(Registration.study_group)
async def enter_study_group(message: Message, state: FSMContext):
    study_group = message.text
    if study_group not in STUDY_GROUPS:
        await message.answer(msg.INVALID_STUDY_GROUP)
        return
    await state.update_data(study_group=study_group)
    await state.set_state(Registration.building)
    await message.answer(msg.CHOOSE_BUILDING, reply_markup=BUILDINGS_ROW_BUTTONS)

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
    if floor not in ROOMS_BY_FLOOR.keys():
        await message.answer(msg.INVALID_FLOOR)
        return
    await state.update_data(floor=floor)
    await state.set_state(Registration.room)
    await message.answer(msg.CHOOSE_ROOM, reply_markup=ROOMS_BY_FLOOR_ROW_BUTTONS[floor])

@router.message(Registration.room)
async def enter_room(message: Message, state: FSMContext):
    room = message.text
    data = await state.get_data()
    floor = data.get("floor")
    if room not in ROOMS_BY_FLOOR[floor]:
        await message.answer(msg.INVALID_ROOM)
        return
    await state.update_data(room=room)
    await state.set_state(Registration.phone_number)
    await message.answer(msg.ENTER_PHONE_NUMBER, reply_markup=ReplyKeyboardRemove())

@router.message(Registration.phone_number)
async def enter_phone_number(message: Message, state: FSMContext):
    try:
        phone_number = PhoneNumberValidator().validate(message)
        await state.update_data(phone_number=phone_number)
        registration_data = await state.get_data()
        await state.clear()

        formatted_registration_data = registration_data.copy()
        formatted_registration_data['room'] = f"0{registration_data['building']}-0{registration_data['entrance']}-{registration_data['room']}"
        del formatted_registration_data['building']
        del formatted_registration_data['entrance']
        del formatted_registration_data['floor']

        async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
            logger.info('Send data to registration queue...')
            exchange = await channel.declare_exchange("registration_exchange", ExchangeType.DIRECT, durable=True)
            queue = await channel.declare_queue('registration_queue', durable=True)
            await queue.bind(exchange, '')

            await exchange.publish(
                aio_pika.Message(
                    msgpack.packb(formatted_registration_data),
                    # correlation_id=correlation_id_ctx.get()
                    # correlation_id=context.get(HeaderKeys.correlation_id)
                ),
                ''
            )

        async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
            queue: Queue = await channel.declare_queue(
                settings.USER_REGISTRATION_QUEUE_TEMPLATE.format(user_id=message.from_user.id),
                durable=True,
            )

            retries = 3
            for _ in range(retries):
                try:
                    registration_flag = await queue.get()
                    parsed_registration_flag: dict[str, Any] = msgpack.unpackb(registration_flag.body)

                    answer = msg.SUCCESS_REGISTER if parsed_registration_flag else msg.ALREADY_REGISTER
                    await message.answer(answer)
                    return
                except QueueEmpty:
                    await asyncio.sleep(1)

    except validation.InvalidPhoneNumberFormatError:
        await message.answer(msg.ENTER_PHONE_NUMBER)
