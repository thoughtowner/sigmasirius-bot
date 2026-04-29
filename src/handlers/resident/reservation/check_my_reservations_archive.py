from aiogram.types import Message, CallbackQuery
from aiogram import F
from aiogram.fsm.context import FSMContext

from ..router import router
from src.commands import CHECK_MY_RESERVATION, CHECK_MY_RESERVATIONS_ARCHIVE, DELETE_RESERVATION
from src.storage.db import async_session
from src.model.models import User, Reservation, ReservationStatus
from sqlalchemy import select
import aio_pika
import msgpack
from aio_pika import ExchangeType
from src.storage.rabbit import channel_pool
from config.settings import settings
from aio_pika.exceptions import QueueEmpty
import asyncio


@router.message(F.text == CHECK_MY_RESERVATIONS_ARCHIVE)
async def check_my_reservations_archive(message: Message, state: FSMContext):
    # user starts a new command -> clear old reservation inline markups
    try:
        from consumers.start_consumer.handlers.start import clear_reservation_markups
        await clear_reservation_markups(message.from_user.id)
    except Exception:
        pass

    telegram_id = message.from_user.id

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            reservations = []
        else:
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status.in_([ReservationStatus.COMPLETED, ReservationStatus.CANCELELLED])))
            reservations = res_q.scalars().all()

    if not reservations:
        await message.answer('Архив пуст')
        try:
            from consumers.start_consumer.handlers.start import send_reply_start_keyboard
            await send_reply_start_keyboard(message.from_user.id, clear_reservation_markups=False)
        except Exception:
            pass
        return

    texts = []
    for r in reservations:
        texts.append(f"ID: {r.id}\nСтатус: {r.status.value}\nГостей: {r.people_quantity}\nКласс: {r.room_class.value}\nЗаезд: {r.check_in_date}\nВыезд: {r.eviction_date}\n")

    await message.answer('\n---\n'.join(texts))

    # send start inline keyboard with bot commands (do not clear reservation markups now)
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(message.from_user.id, clear_reservation_markups=False)
    except Exception:
        pass


@router.callback_query(F.data == 'start_cmd:check_my_reservations_archive')
async def check_my_reservations_archive_via_button(query: CallbackQuery):
    await query.answer()
    # user starts a new command via start keyboard button -> clear old reservation inline markups
    try:
        from consumers.start_consumer.handlers.start import clear_reservation_markups
        await clear_reservation_markups(query.from_user.id)
    except Exception:
        pass

    try:
        await query.message.delete()
    except Exception:
        pass
    telegram_id = query.from_user.id

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            reservations = []
        else:
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status.in_([ReservationStatus.COMPLETED, ReservationStatus.CANCELELLED])))
            reservations = res_q.scalars().all()

    if not reservations:
        await query.message.answer('Архив пуст')
        try:
            from consumers.start_consumer.handlers.start import send_reply_start_keyboard
            await send_reply_start_keyboard(query.from_user.id, clear_reservation_markups=False)
        except Exception:
            pass
        return

    texts = []
    for r in reservations:
        texts.append(f"ID: {r.id}\nСтатус: {r.status.value}\nГостей: {r.people_quantity}\nКласс: {r.room_class.value}\nЗаезд: {r.check_in_date}\nВыезд: {r.eviction_date}\n")

    await query.message.answer('\n---\n'.join(texts))

    # send start inline keyboard with bot commands (do not clear reservation markups now)
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(query.from_user.id, clear_reservation_markups=False)
    except Exception:
        pass
