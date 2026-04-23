from aiogram.types import Message
from aiogram import F
from aiogram.fsm.context import FSMContext

from ..router import router
from src.commands import RESEND_QR
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


@router.message(F.text == RESEND_QR)
async def resend_qr(message: Message, state: FSMContext):
    telegram_id = message.from_user.id

    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'resend_qr',
                'telegram_id': telegram_id,
                'is_test_data': False,
            })),
            settings.RESERVATION_QUEUE_NAME
        )
