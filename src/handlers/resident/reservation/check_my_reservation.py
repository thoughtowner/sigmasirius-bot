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
import io
from src.files_storage.storage_client import images_storage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile


@router.message(F.text == CHECK_MY_RESERVATION)
async def check_my_reservation(message: Message, state: FSMContext):
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
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS])))
            reservations = res_q.scalars().all()

    if not reservations:
        await message.answer('У вас нет текущих броней')
        try:
            from consumers.start_consumer.handlers.start import send_reply_start_keyboard
            await send_reply_start_keyboard(message.from_user.id, clear_reservation_markups=False)
        except Exception:
            pass
        return

    texts = []
    for r in reservations:
        res_text = (
            f"ID: {r.id}\nСтатус: {r.status.value}\nГостей: {r.people_quantity}\nКласс: {r.room_class.value}\nЗаезд: {r.check_in_date}\nВыезд: {r.eviction_date}\n"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data=f'cancel_by_id:{r.id}')]])
        try:
            file_bytes = images_storage.get_file(f"reservation/{r.id}.png")
        except Exception:
            file_bytes = None

        if file_bytes:
            try:
                bio = io.BytesIO(file_bytes)
                bio.seek(0)
                image_file = BufferedInputFile(file=bio.read(), filename='reservation_qr.png')
                sent = await message.answer_photo(photo=image_file, caption='Ваш QR-код для заселения. Покажите его на ресепшене.\n\n' + res_text, reply_markup=kb)
                # store mapping so markups can be cleared later when user runs another command
                try:
                    from src.storage.redis import redis_storage
                    import json
                    member = {'telegram_id': message.from_user.id, 'message_id': sent.message_id}
                    key = f'reservation:{r.id}:members'
                    current_raw = await redis_storage.get(key)
                    if current_raw:
                        try:
                            current = json.loads(current_raw)
                        except Exception:
                            current = []
                    else:
                        current = []
                    current.append(member)
                    await redis_storage.set(key, json.dumps(current))
                    await redis_storage.set(f'reservation_message_map:{message.from_user.id}:{sent.message_id}', str(r.id))
                except Exception:
                    pass
            except Exception:
                await message.answer(res_text)
        else:
            await message.answer(res_text)

    # send start inline keyboard with bot commands (do not clear reservation markups now)
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(message.from_user.id, clear_reservation_markups=False)
    except Exception:
        pass


@router.callback_query(F.data == 'start_cmd:check_my_reservation')
async def check_my_reservation_via_button(query: CallbackQuery):
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
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS])))
            reservations = res_q.scalars().all()

    if not reservations:
        await query.message.answer('У вас нет текущих броней')
        try:
            from consumers.start_consumer.handlers.start import send_reply_start_keyboard
            await send_reply_start_keyboard(query.from_user.id, clear_reservation_markups=False)
        except Exception:
            pass
        return

    texts = []
    for r in reservations:
        res_text = (
            f"ID: {r.id}\nСтатус: {r.status.value}\nГостей: {r.people_quantity}\nКласс: {r.room_class.value}\nЗаезд: {r.check_in_date}\nВыезд: {r.eviction_date}\n"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data=f'cancel_by_id:{r.id}')]])
        try:
            file_bytes = images_storage.get_file(f"reservation/{r.id}.png")
        except Exception:
            file_bytes = None

        if file_bytes:
            try:
                bio = io.BytesIO(file_bytes)
                bio.seek(0)
                image_file = BufferedInputFile(file=bio.read(), filename='reservation_qr.png')
                sent = await query.message.answer_photo(photo=image_file, caption='Ваш QR-код для заселения. Покажите его на ресепшене.\n\n' + res_text, reply_markup=kb)
                try:
                    from src.storage.redis import redis_storage
                    import json
                    member = {'telegram_id': query.from_user.id, 'message_id': sent.message_id}
                    key = f'reservation:{r.id}:members'
                    current_raw = await redis_storage.get(key)
                    if current_raw:
                        try:
                            current = json.loads(current_raw)
                        except Exception:
                            current = []
                    else:
                        current = []
                    current.append(member)
                    await redis_storage.set(key, json.dumps(current))
                    await redis_storage.set(f'reservation_message_map:{query.from_user.id}:{sent.message_id}', str(r.id))
                except Exception:
                    pass
            except Exception:
                await query.message.answer(res_text)
        else:
            await query.message.answer(res_text)

    # send start inline keyboard with bot commands (do not clear reservation markups now)
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(query.from_user.id, clear_reservation_markups=False)
    except Exception:
        pass
