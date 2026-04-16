import asyncio
import aio_pika
import random
import msgpack
from uuid import uuid4
import io

from aio_pika import ExchangeType
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.models import User, Room, Reservation, RoomClass
from src.schema.reservation.reservation import ReservationMessage
from src.schema.start.start import StartMessage
from src.storage.rabbit import channel_pool
from src.files_storage.storage_client import images_storage
from config.settings import settings

from faker import Faker
from datetime import date, datetime, timedelta

import uuid

# from scripts.give_user_admin_role import main as give_user_admin_role


fake = Faker('ru_RU')


USERS_QUANTITY = 8
PUSHED_TELEGRAM_IDS = list(1000000 + i for i in range(USERS_QUANTITY))

ADMIN_TELEGRAM_ID = 1000000
ADMIN_PHONE_NUMBER = "+7 (999) 000-00-00"


def phone_number_generator(start: int = 0):
    """Yield sequential phone numbers in format +7 (999) 000-00-00, +7 (999) 000-00-01, ...

    The local part is treated as a 7-digit integer and formatted as XXX-XX-XX.
    """
    n = start
    while True:
        s = f"{n:07d}"
        yield f"+7 (999) {s[0:3]}-{s[3:5]}-{s[5:7]}"
        n += 1


def generate_phone_list(count: int, start: int):
    gen = phone_number_generator(start)
    return list(next(gen) for _ in range(count))


RESERVATION_IDS = list(str(uuid.uuid4()) for _ in range(USERS_QUANTITY-1))

PHONE_NUMBERS = generate_phone_list(USERS_QUANTITY, start=0)
BASE_TEST_DATA = date(2026, 5, 5)
DATE_FOR_CREATE_RESERVATIONS = [
    {
        "reservation_id": RESERVATION_IDS[0],
        "people_quantity": 1,
        "room_class": RoomClass.ECONOMY.value,
        "check_in_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=1),
        "eviction_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=2),
        "room_number_for_admin": 1
    },
    {
        "reservation_id": RESERVATION_IDS[1],
        "people_quantity": 1,
        "room_class": RoomClass.ECONOMY.value,
        "check_in_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=5),
        "eviction_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=6),
        "room_number_for_admin": 1
    },
    {
        "reservation_id": RESERVATION_IDS[2],
        "people_quantity": 1,
        "room_class": RoomClass.ECONOMY.value,
        "check_in_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=10),
        "eviction_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=11),
        "room_number_for_admin": 1
    },
    {
        "reservation_id": RESERVATION_IDS[3],
        "people_quantity": 1,
        "room_class": RoomClass.ECONOMY.value,
        "check_in_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=15),
        "eviction_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=19),
        "room_number_for_admin": 1
    },
    {
        "reservation_id": RESERVATION_IDS[4],
        "people_quantity": 1,
        "room_class": RoomClass.ECONOMY.value,
        "check_in_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=2),
        "eviction_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=3),
        "room_number_for_admin": 2
    },
    {
        "reservation_id": RESERVATION_IDS[5],
        "people_quantity": 1,
        "room_class": RoomClass.ECONOMY.value,
        "check_in_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=8),
        "eviction_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=10),
        "room_number_for_admin": 2
    },
    {
        "reservation_id": RESERVATION_IDS[6],
        "people_quantity": 1,
        "room_class": RoomClass.ECONOMY.value,
        "check_in_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=13),
        "eviction_date": datetime.strptime(str(BASE_TEST_DATA), '%Y-%m-%d') + timedelta(days=18),
        "room_number_for_admin": 2
    }
]


async def add_test_data(db: AsyncSession):
    for pushed_telegram_id, phone_number in zip(PUSHED_TELEGRAM_IDS, PHONE_NUMBERS):
        start_message = StartMessage(
            event='start',
            telegram_id=pushed_telegram_id,
            is_test_data=True,
            full_name=fake.name(),
            phone_number=phone_number,
        )

        async with channel_pool.acquire() as channel:
            start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
            await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

            await start_exchange.publish(
                aio_pika.Message(msgpack.packb(start_message)),
                routing_key=settings.START_QUEUE_NAME
            )
    await wait_for_users_in_db(db)


async def wait_for_users_in_db(db: AsyncSession):
    created_telegram_ids = set()

    retries = 10
    for _ in range(retries):
        for telegram_id in PUSHED_TELEGRAM_IDS:
            user_id_result = await db.execute(
                select(User.telegram_id).filter(User.telegram_id==telegram_id)
            )
            user_id = user_id_result.scalar()

            if user_id:
                created_telegram_ids.add(user_id)
        if created_telegram_ids == set(PUSHED_TELEGRAM_IDS):
            print('users: OK')
            break
        await asyncio.sleep(1)

    await add_user_admin_role(db)


async def add_user_admin_role(db: AsyncSession):
    user_result = await db.execute(
        select(User.id).filter(User.phone_number == ADMIN_PHONE_NUMBER))
    user_id = user_result.scalar()

    if not user_id:
        print('Пользователь не найден!')
        return

    await db.execute(
        update(User).where(User.id == user_id).values(is_admin=True, got_role_from_date=date.today())
    )
    await db.commit()

    print('Пользователь успешно стал администратором')

    await create_reservations_for_users(db)


async def create_reservations_for_users(db: AsyncSession):
    users_result = await db.execute(
        select(User).where(User.telegram_id.in_(PUSHED_TELEGRAM_IDS))
    )
    users = users_result.scalars().all()
    # create reservations for all non-admin users and map DATE_FOR_CREATE_RESERVATIONS in order
    non_admin_users = [u for u in users if u.telegram_id != ADMIN_TELEGRAM_ID]
    if len(non_admin_users) != len(DATE_FOR_CREATE_RESERVATIONS):
        # If counts mismatch, only create up to the smaller length
        count = min(len(non_admin_users), len(DATE_FOR_CREATE_RESERVATIONS))
    else:
        count = len(DATE_FOR_CREATE_RESERVATIONS)

    for i in range(count):
        user = non_admin_users[i]
        dr = DATE_FOR_CREATE_RESERVATIONS[i]
        create_reservation_message = ReservationMessage(
            event='reservation',
            is_test_data=True,
            reservation_id=dr["reservation_id"],
            telegram_id=user.telegram_id,
            people_quantity=dr["people_quantity"],
            room_class=dr["room_class"],
            check_in_date=str(dr["check_in_date"].date()),
            eviction_date=str(dr["eviction_date"].date())
        )

        async with channel_pool.acquire() as channel:
            # bind the canonical reservation queue to the canonical reservation exchange
            reservation_exchange = await channel.declare_exchange(
                settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
            )
            reservation_queue = await channel.declare_queue(
                settings.RESERVATION_QUEUE_NAME, durable=True
            )
            await reservation_queue.bind(reservation_exchange, routing_key=settings.RESERVATION_QUEUE_NAME)

            await reservation_exchange.publish(
                aio_pika.Message(msgpack.packb(create_reservation_message)),
                routing_key=settings.RESERVATION_QUEUE_NAME
            )

    await wait_for_reservations_in_db(db)


async def wait_for_reservations_in_db(db: AsyncSession):
    # reservation_uuid = uuid.UUID(DATE_FOR_CREATE_RESERVATIONS[i]["reservation_id"])

    # found = False
    # for _ in range(30):
    #     res_check = await db.execute(
    #         select(ReservationModel.__table__.c.id).where(ReservationModel.__table__.c.id == reservation_uuid)
    #     )
    #     if res_check.first():
    #         found = True
    #         break
    #     await asyncio.sleep(0.5)

    # created_users_and_reservations = set()

    # retries = 10
    # for _ in range(retries):
    #     for telegram_id in PUSHED_TELEGRAM_IDS:
    #         user_result = await db.execute(
    #             select(User).filter(User.telegram_id==telegram_id)
    #         )
    #         user = user_result.scalar()

    #         reservation_id_result = await db.execute(
    #             select(Reservation.id).filter(Reservation.user_id==user.id)
    #         )
    #         reservation_id = reservation_id_result.scalar()

    #         if reservation_id:
    #             created_users_and_reservations.add((user.telegram_id, reservation_id))
    #     if created_users_and_reservations == zip(PUSHED_TELEGRAM_IDS, RESERVATION_IDS):
    #         break
    #     await asyncio.sleep(1)

    #     print(user.telegram_id, reservation_id)

    created_reservations = set()

    retries = 10
    for _ in range(retries):
        for reservation_id in RESERVATION_IDS:
            try:
                rid = uuid.UUID(reservation_id)
            except Exception:
                rid = reservation_id
            db_reservation_id_result = await db.execute(
                select(Reservation.id).filter(Reservation.id == rid)
            )
            db_reservation_id = db_reservation_id_result.scalar()

            if db_reservation_id:
                created_reservations.add(str(db_reservation_id))
        if set(created_reservations) == set(RESERVATION_IDS):
            print('reservations: OK')
            break
        await asyncio.sleep(1)

    await confirm_reservations(db)


async def confirm_reservations(db: AsyncSession):
    users_result = await db.execute(
        select(User).where(User.telegram_id.in_(PUSHED_TELEGRAM_IDS))
    )
    users = users_result.scalars().all()
    # operate over non-admin users in same order as DATE_FOR_CREATE_RESERVATIONS
    non_admin_users = [u for u in users if u.telegram_id != ADMIN_TELEGRAM_ID]
    count = min(len(non_admin_users), len(DATE_FOR_CREATE_RESERVATIONS))

    for i in range(count):
        user = non_admin_users[i]
        dr = DATE_FOR_CREATE_RESERVATIONS[i]

        payload = {
            'event': 'check_unconfirmed_reservation',
            'is_test_data': True,
            'reservation_id': dr["reservation_id"],
            'telegram_id': ADMIN_TELEGRAM_ID
        }

        async with channel_pool.acquire() as channel:
            reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            await reservation_exchange.publish(
                aio_pika.Message(msgpack.packb(payload)),
                settings.RESERVATION_QUEUE_NAME
            )

        # After reservation exists, simulate admin assigning a room based on room_number_for_admin
        room_choice = dr.get('room_number_for_admin')
        target_full = '1-1-101' if room_choice == 1 else '1-1-104'

        # wait for reservation row
        reservation_uuid = None
        try:
            reservation_uuid = uuid.UUID(dr["reservation_id"])
        except Exception:
            reservation_uuid = dr["reservation_id"]

        found = False
        for _ in range(30):
            res_check = await db.execute(
                select(Reservation.__table__.c.id).where(Reservation.__table__.c.id == reservation_uuid)
            )
            if res_check.first():
                found = True
                break
            await asyncio.sleep(0.5)

        if found:
            room_q = await db.execute(select(Room).filter(Room.full_room_number == target_full))
            room_obj = room_q.scalar_one_or_none()

            if room_obj:
                assign_payload = {
                    'event': 'assign_room',
                    'is_test_data': True,
                    'reservation_id': dr["reservation_id"],
                    'room_id': str(room_obj.id),
                    'telegram_id': ADMIN_TELEGRAM_ID
                }
                async with channel_pool.acquire() as channel:
                    reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
                    await reservation_exchange.publish(
                        aio_pika.Message(msgpack.packb(assign_payload)),
                        settings.RESERVATION_QUEUE_NAME
                    )


async def main():
    from src.storage.db import async_session
    
    async with async_session() as db:
        await add_test_data(db)


if __name__ == '__main__':
    asyncio.run(main())
