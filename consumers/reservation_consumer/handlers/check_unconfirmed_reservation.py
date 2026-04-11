from config.settings import settings
from ..storage.db import async_session
from ..model.models import User, Reservation, ReservationStatus
from ..storage.rabbit import channel_pool
import aio_pika
from aio_pika import ExchangeType
import msgpack
from datetime import date
import uuid


async def handle_check_unconfirmed_reservation_event(message):
    # support two modes: lookup by phone_number OR lookup by reservation_id from QR
    admin_queue = settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=message.get('telegram_id'))

    print(f"[consumer] handle_check_unconfirmed_reservation_event message={message}")
    async with async_session() as db:
        # If reservation_id provided, find by id
        if message.get('reservation_id'):
            reservation_id = uuid.UUID(message.get('reservation_id'))
            print(f"[consumer] lookup by reservation_id={reservation_id}")
            res_q = await db.execute(
                Reservation.__table__.select().where(
                    (Reservation.__table__.c.id == reservation_id) &
                    (Reservation.__table__.c.status == ReservationStatus.UNCONFIRM) &
                    (Reservation.__table__.c.check_in_date == date.today())
                )
            )
            res_row = res_q.first()

            async with channel_pool.acquire() as ch:
                reservation_exchange = await ch.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
                # ensure admin reply queue exists and is bound to exchange
                reply_queue = await ch.declare_queue(admin_queue, durable=True)
                await reply_queue.bind(reservation_exchange, admin_queue)
                if not res_row:
                    print(f"[consumer] reservation not found for id={reservation_id}")
                    await reservation_exchange.publish(
                        aio_pika.Message(msgpack.packb({'found': False})),
                        admin_queue
                    )
                    return

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

                print(f"[consumer] reservation found id={reservation_id}, publishing payload to admin_queue={admin_queue}")
                await reservation_exchange.publish(
                    aio_pika.Message(msgpack.packb(payload)),
                    admin_queue
                )
                return

        # # fallback to original phone-based flow
        # user_q = await db.execute(
        #     User.__table__.select().where(User.phone_number == message.get('phone_number'))
        # )
        # user_row = user_q.first()

        # if not user_row:
        #     print(f"[consumer] user not found for phone={message.get('phone_number')}")
        #     async with channel_pool.acquire() as ch:
        #         reservation_exchange = await ch.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        #         await reservation_exchange.publish(
        #             aio_pika.Message(msgpack.packb({'found': False})),
        #             admin_queue
        #         )
        #     return

        # user_id = user_row._mapping['id']

        # today = date.today()
        # res_q = await db.execute(
        #     Reservation.__table__.select().where(
        #         (Reservation.__table__.c.user_id == user_id) &
        #         (Reservation.__table__.c.status == ReservationStatus.UNCONFIRM) &
        #         (Reservation.__table__.c.check_in_date == today)
        #     )
        # )
        # res_row = res_q.first()

        # async with channel_pool.acquire() as ch:
        #     reservation_exchange = await ch.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        #     if not res_row:
        #         print(f"[consumer] no reservation found for user_id={user_id} on date={date.today()}")
        #         await reservation_exchange.publish(
        #             aio_pika.Message(msgpack.packb({'found': False})),
        #             admin_queue
        #         )
        #         return

        #     payload = {
        #         'found': True,
        #         'reservation': {
        #             'id': str(res_row._mapping['id']),
        #             'user_id': str(res_row._mapping['user_id']),
        #             'people_quantity': int(res_row._mapping['people_quantity']),
        #             'room_class': res_row._mapping['room_class'].value,
        #             'check_in_date': str(res_row._mapping['check_in_date']),
        #             'eviction_date': str(res_row._mapping['eviction_date']),
        #             'status': res_row._mapping['status'].value
        #         }
        #     }

        #     print(f"[consumer] found reservation for user_id={user_id}, publishing payload to admin_queue={admin_queue}")
        #     await reservation_exchange.publish(
        #         aio_pika.Message(msgpack.packb(payload)),
        #         admin_queue
        #     )
