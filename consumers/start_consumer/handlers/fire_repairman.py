from ...repairman_consumer.storage.db import async_session
from ...repairman_consumer.model.models import User
from sqlalchemy import select, update
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import settings
import aio_pika
import msgpack
from aio_pika import ExchangeType
from ...repairman_consumer.logger import LOGGING_CONFIG, logger
from ...repairman_consumer.storage.rabbit import channel_pool
from aio_pika.exceptions import QueueEmpty
import asyncio

import uuid
from datetime import date


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)


async def handle_fire_repairman_event(message):
    admin_queue = settings.USER_REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=message.get('telegram_id'))

    print(f"[consumer] handle_check_unconfirmed_repairman_event message={message}")
    async with async_session() as db:
        # If repairman_id provided, find by id
        if message.get('repairman_id'):
            repairman_id = uuid.UUID(message.get('repairman_id'))
            print(f"[consumer] lookup by repairman_id={repairman_id}")
            res_q = await db.execute(
                User.__table__.select().where(
                    (User.__table__.c.id == repairman_id),
                )
            )
            res_row = res_q.first()

            async with channel_pool.acquire() as ch:
                repairman_exchange = await ch.declare_exchange(settings.REPAIRMAN_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
                # ensure admin reply queue exists and is bound to exchange
                reply_queue = await ch.declare_queue(admin_queue, durable=True)
                await reply_queue.bind(repairman_exchange, admin_queue)

                from src.bot import bot

                if not res_row:
                    print(f"[consumer] repairman not found for id={repairman_id}")
                    await repairman_exchange.publish(
                        aio_pika.Message(msgpack.packb({'found': False, 'reason': 'not_found'})),
                        admin_queue
                    )
                    
                    await bot.send_message(res_row.telegram_id, 'Возникла ошибка.')
                    return
                elif not res_row.is_repairman:
                    print(f"[consumer] repairman not found for id={repairman_id}")
                    await repairman_exchange.publish(
                        aio_pika.Message(msgpack.packb({'found': False, 'reason': 'repairman'})),
                        admin_queue
                    )
                    
                    await bot.send_message(res_row.telegram_id, 'Вы не являетесь ремонтником!')
                    return

                await db.execute(
                    update(User).where(User.id == repairman_id).values(is_repairman=False, got_role_from_date=date.today())
                )
                await db.commit()

                print(f"[consumer] repairman found id={repairman_id}, publishing payload to admin_queue={admin_queue}")
                await repairman_exchange.publish(
                    aio_pika.Message(msgpack.packb({'found': True})),
                    admin_queue
                )
                
                await bot.send_message(res_row.telegram_id, 'Вы успешно уволены с должности ремонтника!')
                return
