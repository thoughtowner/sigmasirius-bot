from aiogram.types import Message
from aiogram import F
from aiogram.fsm.context import FSMContext

from ..router import router
from src.commands import ASSIGN_REPAIRMAN, REMOVE_REPAIRMAN
from src.storage.db import async_session
from src.model.models import User
from sqlalchemy import select, update
from datetime import date
from src.states.admin import AdminRepairman
import aio_pika
import msgpack
from aio_pika import ExchangeType
from src.storage.rabbit import channel_pool
from config.settings import settings
from aio_pika.exceptions import QueueEmpty
import asyncio


@router.message(F.text == ASSIGN_REPAIRMAN)
async def assign_repairman_start(message: Message, state: FSMContext):
    await state.set_state(AdminRepairman.assign_phone)
    await message.answer('Введите номер телефона пользователя в формате +79991234567')


@router.message(AdminRepairman.assign_phone)
async def handle_assign_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    admin_id = message.from_user.id

    async with channel_pool.acquire() as channel:
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await start_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'assign_repairman',
                'phone_number': phone,
                'admin_telegram_id': admin_id,
            })),
            settings.START_QUEUE_NAME
        )

    # wait for response on admin queue
    async with channel_pool.acquire() as channel:
        user_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id),
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
        await message.answer('Ошибка: нет ответа от сервера, повторите позже')
    else:
        await message.answer(body.get('msg', 'Операция завершена'))

    state_data = await state.get_data()
    await state.clear()
    await state.update_data(state_data)


@router.message(F.text == REMOVE_REPAIRMAN)
async def remove_repairman_start(message: Message, state: FSMContext):
    await state.set_state(AdminRepairman.remove_phone)
    await message.answer('Введите номер телефона пользователя для увольнения ремонтника в формате +79991234567')


@router.message(AdminRepairman.remove_phone)
async def handle_remove_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    admin_id = message.from_user.id

    async with channel_pool.acquire() as channel:
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await start_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'remove_repairman',
                'phone_number': phone,
                'admin_telegram_id': admin_id,
            })),
            settings.START_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:
        user_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id),
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
        await message.answer('Ошибка: нет ответа от сервера, повторите позже')
    else:
        await message.answer(body.get('msg', 'Операция завершена'))

    state_data = await state.get_data()
    await state.clear()
    await state.update_data(state_data)
