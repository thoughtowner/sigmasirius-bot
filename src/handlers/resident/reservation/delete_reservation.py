from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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


@router.message(F.text == DELETE_RESERVATION)
async def delete_reservation(message: Message, state: FSMContext):
    telegram_id = message.from_user.id

    # First, request list of user's current reservations and show them
    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'list_my_reservations',
                'telegram_id': telegram_id,
                'is_test_data': False,
            })),
            settings.RESERVATION_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:
        user_queue = await channel.declare_queue(
            settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=telegram_id),
            durable=True,
        )

        retries = 30
        body = None
        for _ in range(retries):
            try:
                msg = await user_queue.get(no_ack=True)
                body = msgpack.unpackb(msg.body)
                break
            except QueueEmpty:
                await asyncio.sleep(0.5)

    if not body or not body.get('reservations'):
        await message.answer('У вас нет текущих броней')
        return

    texts = []
    for r in body['reservations']:
        texts.append(f"ID: {r['id']}\nСтатус: {r['status']}\nГостей: {r['people_quantity']}\nКласс: {r['room_class']}\nЗаезд: {r['check_in_date']}\nВыезд: {r['eviction_date']}\n")

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Да', callback_data='delete_reservation_confirm:yes'), InlineKeyboardButton(text='Нет', callback_data='delete_reservation_confirm:no')]])

    await message.answer('\n---\n'.join(texts))
    await message.answer('Вы точно хотите удалить свою текущую бронь', reply_markup=kb)



@router.callback_query(F.data.startswith('delete_reservation_confirm:'))
async def handle_delete_reservation_confirm(query: CallbackQuery):
    choice = query.data.split(':', 1)[1]
    telegram_id = query.from_user.id

    await query.answer()

    if choice == 'no':
        await query.message.answer('Операция отменена')
        return

    # User confirmed deletion, send cancel_reservations event
    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'cancel_reservations',
                'telegram_id': telegram_id,
                'is_test_data': False,
            })),
            settings.RESERVATION_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:
        user_queue = await channel.declare_queue(
            settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=telegram_id),
            durable=True,
        )

        retries = 30
        body = None
        for _ in range(retries):
            try:
                msg = await user_queue.get(no_ack=True)
                body = msgpack.unpackb(msg.body)
                break
            except QueueEmpty:
                await asyncio.sleep(0.5)

    if not body:
        await query.message.answer('Ошибка: нет ответа от сервера, повторите позже')
        return

    await query.message.answer(body.get('msg', 'Операция завершена'))
