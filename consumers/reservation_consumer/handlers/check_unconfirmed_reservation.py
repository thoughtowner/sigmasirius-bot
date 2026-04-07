from config.settings import settings
from ..storage.db import async_session
from ..model.models import User, Reservation, ReservationStatus
from ..storage.rabbit import channel_pool
import aio_pika
from aio_pika import ExchangeType
import msgpack
from datetime import date


async def handle_check_unconfirmed_reservation_event(message):
    # message: {'event':'check_unconfirmed_reservation', 'phone_number':..., 'telegram_id': <telegram_id>}
    admin_queue = settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=message.get('telegram_id'))

    async with async_session() as db:
        user_q = await db.execute(
            # phone_number stored unique
            User.__table__.select().where(User.phone_number == message.get('phone_number'))
        )
        user_row = user_q.first()

        if not user_row:
            # reply nothing found
            async with channel_pool.acquire() as ch:
                reservation_exchange = await ch.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
                await reservation_exchange.publish(
                    aio_pika.Message(msgpack.packb({'found': False})),
                    admin_queue
                )
            return

        user_id = user_row._mapping['id']

        today = date.today()
        res_q = await db.execute(
            Reservation.__table__.select().where(
                (Reservation.__table__.c.user_id == user_id) &
                (Reservation.__table__.c.status == ReservationStatus.UNCONFIRM) &
                (Reservation.__table__.c.check_in_date == today)
            )
        )
        res_row = res_q.first()

        async with channel_pool.acquire() as ch:
            reservation_exchange = await ch.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            if not res_row:
                await reservation_exchange.publish(
                    aio_pika.Message(msgpack.packb({'found': False})),
                    admin_queue
                )
                return

            # prepare payload
            payload = {
                'found': True,
                'reservation': {
                    'id': str(res_row._mapping['id']),
                    'user_id': str(res_row._mapping['user_id']),
                    'people_quantity': int(res_row._mapping['people_quantity']),
                    'room_class': res_row._mapping['room_class'].value,
                    'check_in_date': str(res_row._mapping['check_in_date']),
                    'eviction_date': str(res_row._mapping['eviction_date']),
                    'status': res_row._mapping['status'].value
                }
            }

            await reservation_exchange.publish(
                aio_pika.Message(msgpack.packb(payload)),
                admin_queue
            )
