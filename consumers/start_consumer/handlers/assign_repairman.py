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


async def handle_assign_repairman_event(message):
    # repairman_id = message.get('repairman_id')
    # admin_id = message.get('telegram_id')

    # async with async_session() as db:
    #     user_q = await db.execute(select(User).filter(User.phone_number == phone))
    #     user = user_q.scalar_one_or_none()

    #     if not user:
    #         resp = {'msg': 'Пользователь с таким номером не найден'}
    #     elif user.is_admin:
    #         resp = {'msg': 'Пользователь не может быть администратором и ремонтником одновременно!'}
    #     elif user.is_repairman:
    #         resp = {'msg': 'Этот пользователь уже является ремонтником!'}
    #     else:
    #         await db.execute(update(User).where(User.id == user.id).values(is_repairman=True))
    #         await db.commit()
    #         resp = {'msg': 'Пользователю присвоена роль ремонтника'}
    #         try:
    #             await bot.send_message(chat_id=user.telegram_id, text='Вам присвоена роль ремонтника')
    #         except Exception:
    #             logger.exception('Failed to notify user about repairman assignment')

    # # send response back to admin queue
    # async with channel_pool.acquire() as channel:
    #     repairman_exchange = await channel.declare_exchange(settings.REPAIRMAN_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
    #     reverse_queue = await channel.declare_queue(
    #         settings.REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id),
    #         durable=True,
    #     )
    #     await reverse_queue.bind(repairman_exchange, settings.REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id))
    #     await repairman_exchange.publish(
    #         aio_pika.Message(msgpack.packb(resp)),
    #         settings.REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id),
    #     )

    admin_queue = settings.USER_REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=message.get('telegram_id'))

    print(f"[consumer] handle_check_unconfirmed_repairman_event message={message}")
    async with async_session() as db:
        # If repairman_id provided, find by id
        if message.get('repairman_id'):
            repairman_id = uuid.UUID(message.get('repairman_id'))
            print(f"[consumer] lookup by repairman_id={repairman_id}")
            res_q = await db.execute(select(User).filter(User.id == repairman_id))
            res_row = res_q.scalar_one_or_none()

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
                    return
                elif res_row.is_repairman:
                    print(f"[consumer] user already repairman id={repairman_id}")
                    await repairman_exchange.publish(
                        aio_pika.Message(msgpack.packb({'found': False, 'reason': 'repairman'})),
                        admin_queue
                    )
                    try:
                        await bot.send_message(res_row.telegram_id, 'Вы уже являетесь ремонтником.')
                    except Exception:
                        pass
                    return
                elif res_row.is_admin:
                    print(f"[consumer] user is admin id={repairman_id}")
                    await repairman_exchange.publish(
                        aio_pika.Message(msgpack.packb({'found': False, 'reason': 'admin'})),
                        admin_queue
                    )
                    try:
                        await bot.send_message(res_row.telegram_id, 'Вы являетесь администратором. Вы не может иметь несколько ролей.')
                    except Exception:
                        pass
                    return

                await db.execute(
                    update(User).where(User.id == repairman_id).values(is_repairman=True, got_role_from_date=date.today())
                )
                await db.commit()

                print(f"[consumer] repairman found id={repairman_id}, publishing payload to admin_queue={admin_queue}")
                await repairman_exchange.publish(
                    aio_pika.Message(msgpack.packb({'found': True})),
                    admin_queue
                )
                
                await bot.send_message(res_row.telegram_id, 'Вы успешно приняты на должность ремонтника!')
                return


# async def handle_remove_repairman_event(message):
#     phone = message.get('phone_number')
#     admin_id = message.get('telegram_id')

#     async with async_session() as db:
#         user_q = await db.execute(select(User).filter(User.phone_number == phone))
#         user = user_q.scalar_one_or_none()

#         if not user:
#             resp = {'msg': 'Пользователь с таким номером не найден'}
#         elif not user.is_repairman:
#             resp = {'msg': 'Пользователь не является ремонтником!'}
#         else:
#             await db.execute(update(User).where(User.id == user.id).values(is_repairman=False))
#             await db.commit()
#             resp = {'msg': 'Ремонтник уволен'}
#             try:
#                 await bot.send_message(chat_id=user.telegram_id, text='Вы больше не являетесь ремонтником')
#             except Exception:
#                 logger.exception('Failed to notify user about repairman removal')

#     async with channel_pool.acquire() as channel:
#         repairman_exchange = await channel.declare_exchange(settings.REPAIRMAN_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
#         reverse_queue = await channel.declare_queue(
#             settings.USER_REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id),
#             durable=True,
#         )
#         await reverse_queue.bind(repairman_exchange, settings.USER_REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id))
#         await repairman_exchange.publish(
#             aio_pika.Message(msgpack.packb(resp)),
#             settings.USER_REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id),
#         )
