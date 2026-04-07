from ..storage.db import async_session
from ..model.models import Room, Reservation, ReservationStatus, User
from sqlalchemy import select
from config.settings import settings
import aio_pika
import msgpack
from aio_pika import ExchangeType
from ..storage.rabbit import channel_pool
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from ..logger import LOGGING_CONFIG, logger
from src.storage.redis import redis_storage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
from uuid import uuid4
from datetime import date

from consumers.start_consumer.handlers.start import handle_start_event

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)


async def handle_pick_room_event(message):
    reservation_id = message.get('reservation_id')
    admin_id = message.get('telegram_id')
    callback_chat_id = message.get('callback_chat_id')
    callback_message_id = message.get('callback_query_message_id')

    async with async_session() as db:
        res_q = await db.execute(select(Reservation).filter(Reservation.id == reservation_id))
        reservation = res_q.scalar_one_or_none()

        if not reservation:
            try:
                await bot.send_message(chat_id=admin_id, text='Бронь не найдена')
            except Exception:
                logger.exception('Failed to notify admin')
            return

        start_date = reservation.check_in_date
        end_date = reservation.eviction_date

        rooms_q = await db.execute(
            select(Room).filter(
                Room.people_quantity == int(reservation.people_quantity),
                Room.room_class == reservation.room_class,
            )
        )
        rooms = rooms_q.scalars().all()

        if not rooms:
            try:
                await bot.send_message(chat_id=admin_id, text='Нет доступных комнат для выбранных параметров')
            except Exception:
                logger.exception('Failed to notify admin no rooms')
            return

        from collections import defaultdict
        grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for r in rooms:
            grouped[str(r.building)][str(r.entrance)][str(r.flour)].append(r)

        group_token = uuid4().hex[:12]
        sent_message_ids = []

        for building in sorted(grouped.keys(), key=int):
            building_sent = False
            for entrance in sorted(grouped[building].keys(), key=int):
                entrance_rooms = []
                for floor in sorted(grouped[building][entrance].keys(), key=int):
                    entrance_rooms.extend(grouped[building][entrance][floor])

                entrance_buttons = []
                for room in entrance_rooms:
                    overlap_q = await db.execute(
                        select(Reservation).filter(
                            (Reservation.room_id == room.id) &
                            (Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS])) &
                            (Reservation.check_in_date <= end_date) &
                            (Reservation.eviction_date >= start_date)
                        )
                    )
                    conflict = overlap_q.first()

                    if conflict:
                        label = f"{room.full_room_number} ✖️"
                        cb = InlineKeyboardButton(text=label, callback_data='noop')
                    else:
                        label = f"{room.full_room_number}"
                        token = uuid4().hex[:12]
                        await redis_storage.set(f'assign_mapping:{token}', json.dumps({
                            'reservation_id': str(reservation.id),
                            'room_id': str(room.id),
                            'group_token': group_token,
                        }), ex=300)
                        cb = InlineKeyboardButton(text=label, callback_data=f'assign_room:{token}')

                    entrance_buttons.append(cb)

                if not entrance_buttons:
                    continue

                if not building_sent:
                    m_building = await bot.send_message(chat_id=admin_id, text=f'Здание {building}:')
                    sent_message_ids.append(m_building.message_id)
                    building_sent = True

                rows_for_entrance = [entrance_buttons[i:i+4] for i in range(0, len(entrance_buttons), 4)]
                m_ent = await bot.send_message(chat_id=admin_id, text=f'Подъезд {entrance}:', reply_markup=InlineKeyboardMarkup(inline_keyboard=rows_for_entrance))
                sent_message_ids.append(m_ent.message_id)

        # include original callback message id so admin can delete if needed
        if callback_message_id:
            sent_message_ids.insert(0, callback_message_id)

        await redis_storage.set(f'assign_group:{group_token}', json.dumps({
            'chat_id': admin_id,
            'message_ids': sent_message_ids,
        }), ex=300)


async def handle_assign_room_event(message):
    token = message.get('token')
    admin_id = message.get('telegram_id')
    callback_chat_id = message.get('callback_chat_id')
    callback_message_id = message.get('callback_message_id')

    key = f'assign_mapping:{token}'
    mapping_raw = await redis_storage.get(key)
    if not mapping_raw:
        try:
            await bot.send_message(chat_id=admin_id, text='Данные кнопки устарели, повторите выбор')
        except Exception:
            logger.exception('Failed to notify admin mapping missing')
        return

    if isinstance(mapping_raw, (bytes, bytearray)):
        mapping_raw = mapping_raw.decode()

    mapping = json.loads(mapping_raw)
    reservation_id = mapping.get('reservation_id')
    room_id = mapping.get('room_id')
    group_token = mapping.get('group_token')
    await redis_storage.delete(key)

    # fetch and delete group messages
    if group_token:
        group_key = f'assign_group:{group_token}'
        group_raw = await redis_storage.get(group_key)
        if group_raw:
            if isinstance(group_raw, (bytes, bytearray)):
                group_raw = group_raw.decode()
            group = json.loads(group_raw)
            chat_id = group.get('chat_id')
            message_ids = group.get('message_ids', [])
            for mid in message_ids:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=int(mid))
                except Exception:
                    pass
            await redis_storage.delete(group_key)

    async with async_session() as db:
        res_q = await db.execute(select(Reservation).filter(Reservation.id == reservation_id))
        reservation = res_q.scalar_one_or_none()

        room_q = await db.execute(select(Room).filter(Room.id == room_id))
        room = room_q.scalar_one_or_none()

        if not reservation or not room:
            try:
                await bot.send_message(chat_id=admin_id, text='Ошибка при привязке номера')
            except Exception:
                logger.exception('Failed to notify admin assign error')
            return

        # double-check conflicts
        overlap_q = await db.execute(
            select(Reservation).filter(
                (Reservation.room_id == room.id) &
                (Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS])) &
                (Reservation.check_in_date <= reservation.eviction_date) &
                (Reservation.eviction_date >= reservation.check_in_date)
            )
        )
        conflict = overlap_q.first()
        if conflict:
            try:
                await bot.send_message(chat_id=admin_id, text='Номер уже занят на выбранные даты')
            except Exception:
                logger.exception('Failed to notify admin about conflict')
            return

        await db.execute(
            Reservation.__table__.update().where(Reservation.id == reservation.id).values(
                room_id=room.id,
                status=ReservationStatus.IN_PROGRESS
            )
        )
        await db.commit()

        # notify resident
        user_q = await db.execute(select(User).filter(User.id == reservation.user_id))
        user = user_q.scalar_one_or_none()
        if user:
            try:
                await bot.send_message(chat_id=user.telegram_id, text=f'Ваша бронь подтверждена. Номер: {room.full_room_number}')
                if reservation.check_in_date != date.today():
                    res_text_user = (
                        f"Бронь ID: {reservation.id}\n"
                        f"Клиент: {user.phone_number if getattr(user, 'phone_number', None) else ''}\n"
                        f"Количество человек: {reservation.people_quantity}\n"
                        f"Класс номера: {reservation.room_class.value if reservation.room_class else ''}\n"
                        f"Дата заезда: {reservation.check_in_date}\n"
                        f"Дата выезда: {reservation.eviction_date}\n"
                        f"Номер: {room.full_room_number}\n"
                    )
                    await bot.send_message(chat_id=user.telegram_id, text=res_text_user)
            except Exception:
                logger.exception('Failed to notify resident')

    try:
        await bot.send_message(chat_id=admin_id, text='Номер привязан, бронь подтверждена')
    except Exception:
        logger.exception('Failed to notify admin after assign')
    finally:
        await handle_start_event(message=message)
