from ..storage.db import async_session
from ..model.models import User
from sqlalchemy import select, update
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import settings
import aio_pika
import msgpack
from aio_pika import ExchangeType
from ..logger import LOGGING_CONFIG, logger
from ..storage.rabbit import channel_pool
from aio_pika.exceptions import QueueEmpty
import asyncio

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)


async def handle_assign_repairman_event(message):
    phone = message.get('phone_number')
    admin_id = message.get('admin_telegram_id')

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.phone_number == phone))
        user = user_q.scalar_one_or_none()

        if not user:
            resp = {'msg': 'Пользователь с таким номером не найден'}
        elif user.is_admin:
            resp = {'msg': 'Пользователь не может быть администратором и ремонтником одновременно!'}
        elif user.is_repairman:
            resp = {'msg': 'Этот пользователь уже является ремонтником!'}
        else:
            await db.execute(update(User).where(User.id == user.id).values(is_repairman=True))
            await db.commit()
            resp = {'msg': 'Пользователю присвоена роль ремонтника'}
            try:
                await bot.send_message(chat_id=user.telegram_id, text='Вам присвоена роль ремонтника')
            except Exception:
                logger.exception('Failed to notify user about repairman assignment')

    # send response back to admin queue
    async with channel_pool.acquire() as channel:
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        reverse_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id),
            durable=True,
        )
        await reverse_queue.bind(start_exchange, settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id))
        await start_exchange.publish(
            aio_pika.Message(msgpack.packb(resp)),
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id),
        )


async def handle_remove_repairman_event(message):
    phone = message.get('phone_number')
    admin_id = message.get('admin_telegram_id')

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.phone_number == phone))
        user = user_q.scalar_one_or_none()

        if not user:
            resp = {'msg': 'Пользователь с таким номером не найден'}
        elif not user.is_repairman:
            resp = {'msg': 'Пользователь не является ремонтником!'}
        else:
            await db.execute(update(User).where(User.id == user.id).values(is_repairman=False))
            await db.commit()
            resp = {'msg': 'Ремонтник уволен'}
            try:
                await bot.send_message(chat_id=user.telegram_id, text='Вы больше не являетесь ремонтником')
            except Exception:
                logger.exception('Failed to notify user about repairman removal')

    async with channel_pool.acquire() as channel:
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        reverse_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id),
            durable=True,
        )
        await reverse_queue.bind(start_exchange, settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id))
        await start_exchange.publish(
            aio_pika.Message(msgpack.packb(resp)),
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id),
        )
