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
from src.schema.reservation.check_reservation_data import CheckReservationDataMessage
from src.states.reservation import Reservation
from ..router import router
from src.keyboard_buttons.reservation import ROOM_CLASSES_ROW_BUTTONS, CHECK_RESERVATION_DATA_ROW_BUTTONS
from aiogram.types import ReplyKeyboardRemove
from src.messages import reservation as msg
from src.validators.create_reservation.validators import PeopleNumberValidator
from src.validators.create_reservation import errors as validation
from src.keyboard_buttons.texts import ROOM_CLASSES, CHECK_RESERVATION_DATA_ANSWERS
from src.commands import CREATE_RESERVATION
from src.logger import LOGGING_CONFIG, logger
import logging.config
from src.templates.env import render
from datetime import datetime

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
            await message.answer(body['msg'])
            return

        await state.set_state(Reservation.people_quantity)
        await message.answer(msg.ENTER_PEOPLE_QUANTITY)


@router.message(Reservation.people_quantity)
async def enter_people_quantity(message: Message, state: FSMContext):
    answer = msg.CHOOSE_ROOM_CLASS
    reply_markup = None
    try:
        people_quantity = PeopleNumberValidator().validate(message)
        await state.update_data(people_quantity=people_quantity)
        await state.set_state(Reservation.room_class)
        reply_markup = ROOM_CLASSES_ROW_BUTTONS
    except validation.PeopleNumberShouldBeNumber:
        answer = msg.INVALID_PEOPLE_QUANTITY
    except validation.PeopleNumberShouldBeBetweenOneAndFour:
        answer = msg.PEOPLE_QUANTITY_LESS_THAN_ZERO
    finally:
        await message.answer(answer, reply_markup=reply_markup)


@router.message(Reservation.room_class)
async def enter_room_class(message: Message, state: FSMContext):
    room_class = message.text
    if room_class not in ROOM_CLASSES:
        await message.answer(msg.INVALID_ROOM_CLASS)
        return
    await state.update_data(room_class=room_class)
    await state.set_state(Reservation.check_in_date)
    await message.answer(msg.ENTER_CHECK_IN_DATE, reply_markup=ReplyKeyboardRemove())


@router.message(Reservation.check_in_date)
async def enter_check_in_date(message: Message, state: FSMContext):
    date_text = message.text
    try:
        from datetime import datetime
        check_in_date = datetime.strptime(date_text, '%Y-%m-%d').date()
    except Exception:
        await message.answer(msg.INVALID_DATE)
        return
    from datetime import date as _date
    if check_in_date < _date.today():
        await message.answer(msg.DATE_SHOULD_BE_TODAY_OR_LATER)
        return
    await state.update_data(check_in_date=str(check_in_date))
    await state.set_state(Reservation.eviction_date)
    await message.answer(msg.ENTER_EVICTION_DATE)


@router.message(Reservation.eviction_date)
async def enter_eviction_date(message: Message, state: FSMContext):
    date_text = message.text
    try:
        eviction_date = datetime.strptime(date_text, "%Y-%m-%d").date()
    except Exception:
        await message.answer(msg.INVALID_DATE)
        return
    data = await state.get_data()
    check_in_date = datetime.strptime(data["check_in_date"], "%Y-%m-%d").date()
    if eviction_date < check_in_date:
        await message.answer(msg.DATE_SHOULD_BE_TODAY_OR_LATER)
        return
    await state.update_data(eviction_date=str(eviction_date))

    data = await state.get_data()
    reservation_data = CheckReservationDataMessage(
        people_quantity=data['people_quantity'],
        room_class=data['room_class'],
        check_in_date=data['check_in_date'],
        eviction_date=data['eviction_date']
    )
    await state.set_state(Reservation.check_reservation_data)
    await message.answer(render('reservation/check_reservation_data.jinja2', body=reservation_data), reply_markup=CHECK_RESERVATION_DATA_ROW_BUTTONS)


@router.message(Reservation.check_reservation_data)
async def check_reservation_data(message: Message, state: FSMContext):
    date_text = message.text
    if date_text not in CHECK_RESERVATION_DATA_ANSWERS:
        await message.answer(msg.INVALID_CHECK_RESERVATION_DATA_ANSWER)
        return
    if date_text == CHECK_RESERVATION_DATA_ANSWERS[1]:
        await state.set_state(Reservation.people_quantity)
        await message.answer(msg.ENTER_PEOPLE_QUANTITY, reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(msg.RESERVATION_DATA_SAVED, reply_markup=ReplyKeyboardRemove())

    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    reservation_message = ReservationMessage(
        event='reservation',
        telegram_id=data['telegram_id'],
        people_quantity=data['people_quantity'],
        room_class=data['room_class'],
        check_in_date=data['check_in_date'],
        eviction_date=data['eviction_date']
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
