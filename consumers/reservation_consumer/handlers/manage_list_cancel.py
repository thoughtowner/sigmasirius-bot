from ..storage.db import async_session
from ..model.models import User, Reservation, ReservationStatus
from sqlalchemy import select, delete
from config.settings import settings
import aio_pika
import msgpack
from aio_pika import ExchangeType
from ..storage.rabbit import channel_pool
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from ..logger import LOGGING_CONFIG, logger

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)


async def handle_list_my_reservations_event(message):
    telegram_id = message.get('telegram_id')

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            reservations = []
        else:
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS])))
            reservations = res_q.scalars().all()

    serialized = []
    for r in reservations:
        serialized.append({
            'id': str(r.id),
            'status': r.status.value,
            'people_quantity': r.people_quantity,
            'room_class': r.room_class.value,
            'check_in_date': str(r.check_in_date),
            'eviction_date': str(r.eviction_date),
        })

    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        user_queue_name = settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=telegram_id)
        reverse_queue = await channel.declare_queue(user_queue_name, durable=True)
        await reverse_queue.bind(reservation_exchange, user_queue_name)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb({'reservations': serialized})),
            user_queue_name,
        )


async def handle_list_my_reservations_archive_event(message):
    telegram_id = message.get('telegram_id')

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            reservations = []
        else:
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status == ReservationStatus.COMPLETED))
            reservations = res_q.scalars().all()

    serialized = []
    for r in reservations:
        serialized.append({
            'id': str(r.id),
            'status': r.status.value,
            'people_quantity': r.people_quantity,
            'room_class': r.room_class.value,
            'check_in_date': str(r.check_in_date),
            'eviction_date': str(r.eviction_date),
        })

    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        user_queue_name = settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=telegram_id)
        reverse_queue = await channel.declare_queue(user_queue_name, durable=True)
        await reverse_queue.bind(reservation_exchange, user_queue_name)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb({'reservations': serialized})),
            user_queue_name,
        )


async def handle_cancel_reservations_event(message):
    telegram_id = message.get('telegram_id')

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            resp = {'msg': 'Пользователь не найден'}
        else:
            del_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status.in_([ReservationStatus.UNCONFIRM, ReservationStatus.IN_PROGRESS])))
            reservations = del_q.scalars().all()
            if not reservations:
                resp = {'msg': 'Нет броней для удаления'}
            else:
                for r in reservations:
                    await db.delete(r)
                await db.commit()
                resp = {'msg': 'Ваши текущие брони удалены'}

    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        user_queue_name = settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=telegram_id)
        reverse_queue = await channel.declare_queue(user_queue_name, durable=True)
        await reverse_queue.bind(reservation_exchange, user_queue_name)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb(resp)),
            user_queue_name,
        )
