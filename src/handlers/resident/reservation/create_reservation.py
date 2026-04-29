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
from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import date, timedelta
from src.storage.db import async_session
from src.model.models import Room, Reservation as _Reservation, ReservationStatus, RoomClass
from sqlalchemy import select, exists, func
from src.messages import reservation as msg
from src.validators.create_reservation.validators import PeopleNumberValidator
from src.validators.create_reservation import errors as validation
from src.keyboard_buttons.texts import ROOM_CLASSES, CHECK_RESERVATION_DATA_ANSWERS
from src.commands import CREATE_RESERVATION
from src.logger import LOGGING_CONFIG, logger
import logging.config
from src.msg_templates.env import render
from datetime import datetime
# handle_start_event imported lazily where needed to avoid circular imports

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


async def _append_message_id(state: FSMContext, msg):
    try:
        data = await state.get_data()
    except Exception:
        data = {}
    ids = data.get('message_ids', []) or []
    mid = getattr(msg, 'message_id', None)
    if mid is None:
        try:
            mid = msg.message_id
        except Exception:
            mid = None
    if mid:
        ids.append(mid)
        await state.update_data(message_ids=ids)


async def _delete_tracked_messages(state: FSMContext, bot, chat_id):
    data = await state.get_data() or {}
    ids = data.get('message_ids', []) or []
    try:
        for mid in ids:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass
    finally:
        try:
            await state.update_data(message_ids=[])
        except Exception:
            pass


async def _remove_last_question_markup(state: FSMContext, bot, chat_id):
    try:
        data = await state.get_data() or {}
    except Exception:
        data = {}
    mid = data.get('last_question_message_id')
    if not mid:
        return
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=int(mid), reply_markup=None)
    except Exception:
        pass
    try:
        await state.update_data(last_question_message_id=None)
    except Exception:
        pass

@router.message(F.text == CREATE_RESERVATION)
async def start_reservation(message: Message, state: FSMContext):
    # user is starting a new command => clear old reservation inline markups
    try:
        from consumers.start_consumer.handlers.start import clear_reservation_markups
        await clear_reservation_markups(message.from_user.id)
    except Exception:
        pass
    await state.update_data(telegram_id=message.from_user.id)
    await state.update_data(role='resident')
    await state.set_state(Reservation.people_quantity)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
    resp = await message.answer(msg.ENTER_PEOPLE_QUANTITY, reply_markup=kb)
    await _append_message_id(state, message)
    await _append_message_id(state, resp)
    try:
        await state.update_data(last_question_message_id=resp.message_id)
    except Exception:
        pass


@router.callback_query(F.data == 'start_cmd:create_reservation')
async def start_reservation_via_button(query: CallbackQuery, state: FSMContext):
    await query.answer()
    # user is starting a new command via start keyboard button -> clear old reservation inline markups
    try:
        from consumers.start_consumer.handlers.start import clear_reservation_markups
        await clear_reservation_markups(query.from_user.id)
    except Exception:
        pass
    # delete start inline keyboard message to prevent reuse
    try:
        await query.message.delete()
    except Exception:
        pass

    await state.update_data(telegram_id=query.from_user.id)
    await state.update_data(role='resident')
    # track the inline starter message so it can be deleted
    await _append_message_id(state, query.message)
    await state.set_state(Reservation.people_quantity)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
    resp = await query.message.answer(msg.ENTER_PEOPLE_QUANTITY, reply_markup=kb)
    await _append_message_id(state, resp)
    try:
        await state.update_data(last_question_message_id=resp.message_id)
    except Exception:
        pass


@router.message(Reservation.people_quantity)
async def enter_people_quantity(message: Message, state: FSMContext):
    # cancel
    if message.text == 'Отмена':
        # delete tracked messages on cancel, then clear state
        await _delete_tracked_messages(state, message.bot, message.from_user.id)
        await state.clear()
        return

    await _append_message_id(state, message)
    try:
        await _remove_last_question_markup(state, message.bot, message.from_user.id)
    except Exception:
        pass

    answer = msg.CHOOSE_ROOM_CLASS
    reply_markup = None
    try:
        people_quantity = PeopleNumberValidator().validate(message)
        await state.update_data(people_quantity=people_quantity)
        await state.set_state(Reservation.room_class)
        # build inline keyboard for room classes
        rows = [[InlineKeyboardButton(text=rc, callback_data=f'room_class:{rc}')] for rc in ROOM_CLASSES]
        # add cancel inline button
        rows.append([InlineKeyboardButton(text='Отменить', callback_data='cancel_state')])
        reply_markup = InlineKeyboardMarkup(inline_keyboard=rows)
    except validation.PeopleNumberShouldBeNumber:
        answer = msg.INVALID_PEOPLE_QUANTITY
    except validation.PeopleNumberShouldBeBetweenOneAndFour:
        answer = msg.PEOPLE_QUANTITY_LESS_THAN_ZERO
    finally:
        resp = await message.answer(answer, reply_markup=reply_markup)
        await _append_message_id(state, resp)
        try:
            await state.update_data(last_question_message_id=resp.message_id)
        except Exception:
            pass


@router.callback_query(F.data.startswith('room_class:'))
async def handle_room_class_callback(query: CallbackQuery, state: FSMContext):
    await query.answer()
    room_class = query.data.split(':', 1)[1]
    if room_class not in ROOM_CLASSES:
        try:
            await query.message.answer(msg.INVALID_ROOM_CLASS)
        except Exception:
            pass
        return

    # delete the question message with inline buttons
    try:
        await query.message.delete()
    except Exception:
        pass

    await state.update_data(room_class=room_class)
    await state.set_state(Reservation.nights)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
    resp = await query.message.answer(msg.ENTER_NIGHTS, reply_markup=kb)
    await _append_message_id(state, resp)
    try:
        await state.update_data(last_question_message_id=resp.message_id)
    except Exception:
        pass
    # user reply (none yet) will be tracked when received


@router.message(Reservation.nights)
async def enter_nights(message: Message, state: FSMContext):
    # cancel
    if message.text == 'Отмена':
        await _delete_tracked_messages(state, message.bot, message.from_user.id)
        await state.clear()
        return

    await _append_message_id(state, message)
    try:
        await _remove_last_question_markup(state, message.bot, message.from_user.id)
    except Exception:
        pass

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
    resp = await message.answer('Выберите дату заезда:', reply_markup=kb)
    await _append_message_id(state, resp)
    try:
        await state.update_data(last_question_message_id=resp.message_id)
    except Exception:
        pass


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
        resp = await query.message.answer('Выберите дату заезда:', reply_markup=kb)
        await _append_message_id(state, resp)
        try:
            await state.update_data(last_question_message_id=resp.message_id)
        except Exception:
            pass


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

        rooms_count_q = await db.execute(
            select(func.count()).select_from(Room).where(
                Room.people_quantity == pq,
                Room.room_class == rc,
            )
        )
        total_rooms = rooms_count_q.scalar_one()

        conflicts_q = await db.execute(
            select(func.count()).select_from(_Reservation).where(
                _Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS]),
                _Reservation.check_in_date <= eviction,
                _Reservation.eviction_date >= check_in,
                _Reservation.people_quantity == pq,
                _Reservation.room_class == rc,
            )
        )
        conflicts = conflicts_q.scalar_one()

        available = (total_rooms > conflicts)

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
        reservation_id=str(reservation_id),
        telegram_id=data['telegram_id'],
        people_quantity=people_quantity,
        room_class=room_class,
        check_in_date=check_in.isoformat(),
        eviction_date=eviction.isoformat(),
        is_test_data=False
    )

    async with channel_pool.acquire() as channel:
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

    # await query.message.answer(msg.RESERVATION_DATA_SAVED)
    # delete tracked messages and clear state; do not show selection keyboard
    data = await state.get_data()
    await _delete_tracked_messages(state, query.message.bot, data['telegram_id'])
    await state.clear()
    await state.update_data(data)


# @router.callback_query(F.data == 'noop')
# async def handle_noop(query: CallbackQuery):
#     await query.answer('Доступно лишь для просмотра', show_alert=False)



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
        # check availability for this date: count rooms and conflicting reservations
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

            rooms_count_q = await db.execute(
                select(func.count()).select_from(Room).where(
                    Room.people_quantity == pq,
                    Room.room_class == rc,
                )
            )
            total_rooms = rooms_count_q.scalar_one()

            conflicts_q = await db.execute(
                select(func.count()).select_from(_Reservation).where(
                    _Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS]),
                    _Reservation.check_in_date <= eviction,
                    _Reservation.eviction_date >= check_in,
                    _Reservation.people_quantity == pq,
                    _Reservation.room_class == rc,
                )
            )
            conflicts = conflicts_q.scalar_one()

            available = (total_rooms > conflicts)

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
    # cancel button
    rows.append([InlineKeyboardButton(text='Отмена', callback_data='cancel_reservation')])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == 'cancel_reservation')
async def handle_cancel_reservation_calendar(query: CallbackQuery, state: FSMContext):
    await query.answer()
    # delete tracked messages and clear state; show selection reply keyboard
    await _delete_tracked_messages(state, query.bot, query.from_user.id)
    await state.clear()
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(query.from_user.id)
    except Exception:
        pass
    return


@router.callback_query(F.data == 'cancel_state')
async def handle_cancel_state_from_inline(query: CallbackQuery, state: FSMContext):
    await query.answer()
    # delete tracked messages and clear state; show selection reply keyboard
    await _delete_tracked_messages(state, query.bot, query.from_user.id)
    await state.clear()
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(query.from_user.id)
    except Exception:
        pass
    return


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
#         reservation_id=str(reservation_id),
#         telegram_id=data['telegram_id'],
#         people_quantity=data['people_quantity'],
#         room_class=data['room_class'],
#         check_in_date=data['check_in_date'],
#         eviction_date=data['eviction_date']
#     )

#     async with channel_pool.acquire() as channel:
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
