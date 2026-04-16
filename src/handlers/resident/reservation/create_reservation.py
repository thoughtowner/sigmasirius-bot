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
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import date, timedelta
from src.storage.db import async_session
from src.model.models import Room, Reservation as _Reservation, ReservationStatus, RoomClass
from sqlalchemy import select, exists
from src.messages import reservation as msg
from src.validators.create_reservation.validators import PeopleNumberValidator
from src.validators.create_reservation import errors as validation
from src.keyboard_buttons.texts import ROOM_CLASSES, CHECK_RESERVATION_DATA_ANSWERS
from src.commands import CREATE_RESERVATION
from src.logger import LOGGING_CONFIG, logger
import logging.config
from src.msg_templates.env import render
from datetime import datetime

from aio_pika.exceptions import QueueEmpty
import asyncio

import uuid
import io
import qrcode
from aiogram.types import BufferedInputFile
from src.keyboard_buttons.qr import main_keyboard


logging.config.dictConfig(LOGGING_CONFIG)

# short weekday names in Russian (Monday=0)
WEEKDAY_RU = ('Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс')

@router.message(F.text == CREATE_RESERVATION)
async def start_reservation(message: Message, state: FSMContext):
    await state.update_data(telegram_id=message.from_user.id)
    await state.update_data(role='resident')

    data = await state.get_data()
    check_reservation_message = CheckReservationMessage(
        event='check_reservation',
        is_test_data=False,
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
    await state.set_state(Reservation.nights)
    await message.answer(msg.ENTER_NIGHTS, reply_markup=ReplyKeyboardRemove())


@router.message(Reservation.nights)
async def enter_nights(message: Message, state: FSMContext):
    try:
        nights = int(message.text)
        if nights <= 0:
            raise ValueError()
    except Exception:
        await message.answer(msg.INVALID_NIGHTS)
        return

    await state.update_data(nights=nights)
    await state.update_data(week_offset=0)
    data = await state.get_data()
    people_quantity = data['people_quantity']
    room_class = data['room_class']

    kb = await _build_week_keyboard(0, people_quantity, room_class, nights)
    await state.set_state(Reservation.select_date)
    await message.answer('Выберите дату заезда:', reply_markup=kb)


@router.callback_query(F.data.startswith('reserve_week:'))
async def handle_reserve_week(query: CallbackQuery, state: FSMContext):
    await query.answer()
    try:
        week_offset = int(query.data.split(':', 1)[1])
    except Exception:
        return

    data = await state.get_data()
    people_quantity = data.get('people_quantity')
    room_class = data.get('room_class')
    nights = data.get('nights')
    if people_quantity is None or room_class is None or nights is None:
        await query.message.answer('Ошибка состояния. Повторите команду /create_reservation')
        return

    kb = await _build_week_keyboard(week_offset, people_quantity, room_class, nights)
    await state.update_data(week_offset=week_offset)
    try:
        await query.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        await query.message.answer('Обновление календаря...')
        await query.message.answer('Выберите дату заезда:', reply_markup=kb)


@router.callback_query(F.data.startswith('reserve_date:'))
async def handle_reserve_date(query: CallbackQuery, state: FSMContext):
    await query.answer()
    date_iso = query.data.split(':', 1)[1]
    try:
        check_in = datetime.strptime(date_iso, '%Y-%m-%d').date()
    except Exception:
        await query.message.answer('Неверная дата')
        return

    data = await state.get_data()
    people_quantity = data.get('people_quantity')
    room_class = data.get('room_class')
    nights = data.get('nights')
    if people_quantity is None or room_class is None or nights is None:
        await query.message.answer('Ошибка состояния. Повторите команду /create_reservation')
        return

    eviction = check_in + timedelta(days=nights)

    # Check availability one more time before creating reservation (quick check)
    available = False
    async with async_session() as db:
        try:
            pq = int(people_quantity)
        except Exception:
            pq = int(str(people_quantity))

        try:
            rc = RoomClass(room_class)
        except Exception:
            rc = RoomClass[room_class.upper()]

        conflict_sel_quick = select(_Reservation.room_id).where(
            _Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS]),
            _Reservation.check_in_date <= eviction,
            _Reservation.eviction_date >= check_in
        )

        rooms_q = await db.execute(
            select(Room).where(
                Room.people_quantity == pq,
                Room.room_class == rc,
                ~Room.id.in_(conflict_sel_quick)
            )
        )

        available = rooms_q.scalars().first() is not None

    if not available:
        await query.message.answer('К сожалению, нет свободных номеров на выбранные даты. Выберите другую дату.')
        return

    # remove the calendar message so user cannot pick again
    try:
        await query.message.delete()
    except Exception:
        logger.exception('Failed to delete reservation selection message')

    # send reservation message to reservation queue (consumer will create reservation)
    data = await state.get_data()
    reservation_id = uuid.uuid4()
    reservation_message = ReservationMessage(
        event='reservation',
        is_test_data=False,
        reservation_id=str(reservation_id),
        telegram_id=data['telegram_id'],
        people_quantity=people_quantity,
        room_class=room_class,
        check_in_date=check_in.isoformat(),
        eviction_date=eviction.isoformat()
    )

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to reservation queue...')
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        reservation_queue = await channel.declare_queue(settings.RESERVATION_QUEUE_NAME, durable=True)
        await reservation_queue.bind(reservation_exchange, settings.RESERVATION_QUEUE_NAME)

        await reservation_exchange.publish(
            aio_pika.Message(
                msgpack.packb(reservation_message),
            ),
            settings.RESERVATION_QUEUE_NAME
        )

    await query.message.answer(msg.RESERVATION_DATA_SAVED)
    
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)


@router.callback_query(F.data == 'noop')
async def handle_noop(query: CallbackQuery):
    await query.answer('Доступно лишь для просмотра', show_alert=False)



async def _build_week_keyboard(week_offset: int, people_quantity: int, room_class: str, nights: int):
    today = date.today()
    weekday = today.weekday()  # Monday=0
    if week_offset == 0:
        start = today
        # end is Sunday
        end = today + timedelta(days=(6 - weekday))
    else:
        # start from Monday of that week
        start = today + timedelta(days=(7 * week_offset - weekday))
        end = start + timedelta(days=6)

    rows = []
    current = start
    while current <= end:
        # check availability for this date: exists a room matching params with no overlapping reservation
        check_in = current
        eviction = check_in + timedelta(days=nights)
        available = False
        async with async_session() as db:
            try:
                pq = int(people_quantity)
            except Exception:
                pq = int(str(people_quantity))

            try:
                rc = RoomClass(room_class)
            except Exception:
                rc = RoomClass[room_class.upper()]

            # build subquery of rooms that have conflicting reservations for the requested period
            conflict_sel = select(_Reservation.room_id).where(
                _Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS]),
                _Reservation.check_in_date <= eviction,
                _Reservation.eviction_date >= check_in
            )

            rooms_q = await db.execute(
                select(Room).where(
                    Room.people_quantity == pq,
                    Room.room_class == rc,
                    ~Room.id.in_(conflict_sel)
                )
            )

            available = rooms_q.scalars().first() is not None

        # only include buttons for available dates
        if available:
            iso = current.isoformat()
            weekday = WEEKDAY_RU[current.weekday()]
            label = f"{iso} ({weekday})"
            cb = InlineKeyboardButton(text=label, callback_data=f'reserve_date:{iso}')
            rows.append([cb])
        current += timedelta(days=1)

    # navigation
    nav_row = []
    if week_offset > 0:
        nav_row.append(InlineKeyboardButton(text='Назад', callback_data=f'reserve_week:{week_offset-1}'))
    nav_row.append(InlineKeyboardButton(text='Вперёд', callback_data=f'reserve_week:{week_offset+1}'))
    rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


# @router.message(Reservation.check_in_date)
# async def enter_check_in_date(message: Message, state: FSMContext):
#     date_text = message.text
#     try:
#         from datetime import datetime
#         check_in_date = datetime.strptime(date_text, '%Y-%m-%d').date()
#     except Exception:
#         await message.answer(msg.INVALID_DATE)
#         return
#     from datetime import date as _date
#     if check_in_date < _date.today():
#         await message.answer(msg.DATE_SHOULD_BE_TODAY_OR_LATER)
#         return
#     await state.update_data(check_in_date=str(check_in_date))
#     await state.set_state(Reservation.eviction_date)
#     await message.answer(msg.ENTER_EVICTION_DATE)


# @router.message(Reservation.eviction_date)
# async def enter_eviction_date(message: Message, state: FSMContext):
#     date_text = message.text
#     try:
#         eviction_date = datetime.strptime(date_text, "%Y-%m-%d").date()
#     except Exception:
#         await message.answer(msg.INVALID_DATE)
#         return
#     data = await state.get_data()
#     check_in_date = datetime.strptime(data["check_in_date"], "%Y-%m-%d").date()
#     if eviction_date < check_in_date:
#         await message.answer(msg.EVICION_DAYE_NOT_SHOULD_BE_LESS_THAN_CHECK_IN_DATE)
#         return
#     await state.update_data(eviction_date=str(eviction_date))

#     data = await state.get_data()
#     reservation_data = CheckReservationDataMessage(
#         people_quantity=data['people_quantity'],
#         room_class=data['room_class'],
#         check_in_date=data['check_in_date'],
#         eviction_date=data['eviction_date']
#     )
#     await state.set_state(Reservation.check_reservation_data)
#     await message.answer(render('reservation/check_reservation_data.jinja2', body=reservation_data), reply_markup=CHECK_RESERVATION_DATA_ROW_BUTTONS)


# @router.message(Reservation.check_reservation_data)
# async def check_reservation_data(message: Message, state: FSMContext):
#     date_text = message.text
#     if date_text not in CHECK_RESERVATION_DATA_ANSWERS:
#         await message.answer(msg.INVALID_CHECK_RESERVATION_DATA_ANSWER)
#         return
#     if date_text == CHECK_RESERVATION_DATA_ANSWERS[1]:
#         await state.set_state(Reservation.people_quantity)
#         await message.answer(msg.ENTER_PEOPLE_QUANTITY, reply_markup=ReplyKeyboardRemove())
#         return
#     await message.answer(msg.RESERVATION_DATA_SAVED, reply_markup=ReplyKeyboardRemove())

#     data = await state.get_data()
#     await state.clear()
#     await state.update_data(data)

#     reservation_id = uuid.uuid4()
#     logger.info('{reservation_id}')

#     reservation_message = ReservationMessage(
#         event='reservation',
#         is_test_data=False,
#         reservation_id=str(reservation_id),
#         telegram_id=data['telegram_id'],
#         people_quantity=data['people_quantity'],
#         room_class=data['room_class'],
#         check_in_date=data['check_in_date'],
#         eviction_date=data['eviction_date']
#     )

#     async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
#         logger.info('Send data to reservation queue...')
#         reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
#         reservation_queue = await channel.declare_queue(settings.RESERVATION_QUEUE_NAME, durable=True)
#         await reservation_queue.bind(reservation_exchange, settings.RESERVATION_QUEUE_NAME)

#         await reservation_exchange.publish(
#             aio_pika.Message(
#                 msgpack.packb(reservation_message),
#                 # correlation_id=correlation_id_ctx.get()
#             ),
#             settings.RESERVATION_QUEUE_NAME
#         )
