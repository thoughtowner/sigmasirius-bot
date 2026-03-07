from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context
from consumers.reservation_consumer.logger import correlation_id_ctx

from config.settings import settings
from src.schema.reservation.reservation import ReservationMessage
from src.schema.reservation.check_reservation import CheckReservationMessage
from src.states.reservation import Reservation
from ..router import router
from src.keyboard_buttons.reservation import BUILDINGS_ROW_BUTTONS, ENTRANCES_ROW_BUTTONS, FLOORS_ROW_BUTTONS, ROOM_NUMBERS_BY_FLOOR_ROW_BUTTONS
from aiogram.types import ReplyKeyboardRemove
from src.messages import reservation as msg
from src.keyboard_buttons.texts import BUILDINGS, ENTRANCES, ROOM_NUMBERS_BY_FLOOR
from src.commands import CREATE_RESERVATION
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == CREATE_RESERVATION)
async def start_reservation(message: Message, state: FSMContext):
    await state.update_data(telegram_id=message.from_user.id)
    await state.update_data(role='resident')

    data = await state.get_data()
    check_reservation_message = CheckReservationMessage(
        event='check_reservation',
        telegram_id=data['telegram_id'],
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to reservation queue for check reservation status...')
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        reservation_queue = await channel.declare_queue(settings.RESERVATION_QUEUE_NAME, durable=True)
        await reservation_queue.bind(reservation_exchange, settings.RESERVATION_QUEUE_NAME)

        await reservation_exchange.publish(
            aio_pika.Message(
                msgpack.packb(check_reservation_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.RESERVATION_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        user_reservation_queue = await channel.declare_queue(
            settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=message.from_user.id),
            durable=True,
        )

        retries = 100
        for _ in range(retries):
            try:
                reservation_response_message = await user_reservation_queue.get(no_ack=True)
                body = msgpack.unpackb(reservation_response_message.body)
                break
            except QueueEmpty:
                await asyncio.sleep(1)

        if not body['flag']:
            await message.answer(msg.ALREADY_REGISTER)
            return

    await state.set_state(Reservation.full_name)
    await message.answer(msg.ENTER_FULL_NAME)

# @router.message(Reservation.full_name)
# async def enter_full_name(message: Message, state: FSMContext):
#     answer = msg.ENTER_PHONE_NUMBER
#     try:
#         full_name = FullNameValidator().validate(message)
#         await state.update_data(full_name=full_name)
#         await state.set_state(Reservation.phone_number)
#     except validation.FullNameCannotContainMultipleSpacesError:
#         answer = msg.FULL_NAME_CANNOT_CONTAIN_MULTIPLE_SPACES
#     except validation.InvalidFullNameFormatError:
#         answer = msg.INVALID_FULL_NAME_FORMAT
#     except validation.NameShouldContainOnlyLettersError:
#         answer = msg.NAME_SHOULD_CONTAIN_ONLY_LETTERS
#     except validation.TooLongNameError:
#         answer = msg.TOO_LONG_NAME
#     except validation.TooShortNameError:
#         answer = msg.TOO_SHORT_NAME
#     except validation.NameBeginCannotBeLowercaseError:
#         answer = msg.NAME_BEGIN_CANNOT_BE_LOWER
#     finally:
#         await message.answer(answer)

# @router.message(Reservation.phone_number)
# async def enter_phone_number(message: Message, state: FSMContext):
#     answer = msg.CHOOSE_BUILDING
#     reply_markup=None
#     try:
#         phone_number = PhoneNumberValidator().validate(message)
#         await state.update_data(phone_number=phone_number)
#         await state.set_state(Reservation.building)
#         reply_markup = BUILDINGS_ROW_BUTTONS
#     except validation.InvalidPhoneNumberFormatError:
#         answer = msg.INVALID_PHONE_NUMBER_FORMAT
#     finally:
#         await message.answer(answer, reply_markup=reply_markup)

@router.message(Reservation.building)
async def enter_building(message: Message, state: FSMContext):
    building = message.text
    if building not in BUILDINGS:
        await message.answer(msg.INVALID_BUILDING)
        return
    await state.update_data(building=building)
    await state.set_state(Reservation.entrance)
    await message.answer(msg.CHOOSE_ENTRANCE, reply_markup=ENTRANCES_ROW_BUTTONS)

@router.message(Reservation.entrance)
async def enter_entrance(message: Message, state: FSMContext):
    entrance = message.text
    if entrance not in ENTRANCES:
        await message.answer(msg.INVALID_ENTRANCE)
        return
    await state.update_data(entrance=entrance)
    await state.set_state(Reservation.floor)
    await message.answer(msg.CHOOSE_FLOOR, reply_markup=FLOORS_ROW_BUTTONS)

@router.message(Reservation.floor)
async def enter_floor(message: Message, state: FSMContext):
    floor = message.text
    if floor not in ROOM_NUMBERS_BY_FLOOR.keys():
        await message.answer(msg.INVALID_FLOOR)
        return
    await state.update_data(floor=floor)
    await state.set_state(Reservation.room_number)
    await message.answer(msg.CHOOSE_ROOM_NUMBER, reply_markup=ROOM_NUMBERS_BY_FLOOR_ROW_BUTTONS[floor])

@router.message(Reservation.room_number)
async def enter_room_number(message: Message, state: FSMContext):
    room_number = message.text
    data_without_room_number = await state.get_data()
    floor = data_without_room_number.get('floor')
    if room_number not in ROOM_NUMBERS_BY_FLOOR[floor]:
        await message.answer(msg.INVALID_ROOM_NUMBER)
        return
    await state.update_data(room_number=room_number)
    data = await state.get_data()
    await message.answer(msg.PUSH_DATA_TO_RESERVATION_QUERY, reply_markup=ReplyKeyboardRemove())

    state_data = await state.get_data()
    await state.clear()
    await state.update_data(state_data)

    reservation_message = ReservationMessage(
        event='reservation',
        telegram_id=data['telegram_id'],
        full_name=data['full_name'],
        phone_number=data['phone_number'],
        room=f"0{data['building']}-0{data['entrance']}-{data['room_number']}"
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to reservation queue...')
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        reservation_queue = await channel.declare_queue(settings.RESERVATION_QUEUE_NAME, durable=True)
        await reservation_queue.bind(reservation_exchange, settings.RESERVATION_QUEUE_NAME)

        await reservation_exchange.publish(
            aio_pika.Message(
                msgpack.packb(reservation_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.RESERVATION_QUEUE_NAME
        )
