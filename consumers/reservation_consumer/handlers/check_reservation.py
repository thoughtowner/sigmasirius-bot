from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm, Reservation, ReservationStatus
from sqlalchemy import select, exists

from ..schema import CheckReservationMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.msg_templates.env import render

import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_check_reservation_event(message): # TODO async def handle_check_reservation_event(message: CheckReservationMessage)
    async with async_session() as db:
        user_id_query = await db.execute(
            select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_id_query.scalar()

        user_query = await db.execute(select(User).filter(User.id == user_id))
        user = user_query.scalar()

        if not user:
            flag = False
            msg = 'Чтобы начать пользоваться ботом, выполните команду /start!'
            logger.info('User is not enter /start command: %s', message)
        elif user.is_admin or user.is_repairman:
            flag = False
            msg = 'Бронирование могут создавать только гости отеля!'
            logger.info('User is not eligible to create reservation: %s', message)
        else:
            existing_res_query = await db.execute(
                select(
                    exists().where(
                        (Reservation.user_id == user_id) &
                        (
                            (Reservation.status == ReservationStatus.UNCONFIRM) |
                            (Reservation.status == ReservationStatus.IN_PROGRESS)
                        )
                    )
                )
            )

            existing_res = existing_res_query.scalar()

            if existing_res:
                flag = False
                msg = 'У Вас уже есть незавершённая бронь!'
                logger.info('User already has an active reservation: %s', message)
            else:
                flag = True
                msg = ''
                logger.info('User is resident and may create reservation: %s', message)

        async with channel_pool.acquire() as _channel:
            reservation_exchange = await _channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            user_reservation_queue = await _channel.declare_queue(
                settings.USER_RESERVATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                ),
                durable=True,
            )
            await user_reservation_queue.bind(
                reservation_exchange,
                settings.USER_RESERVATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                )
            )
            await reservation_exchange.publish(
                aio_pika.Message(msgpack.packb({'flag': flag, 'msg': msg})),
                settings.USER_RESERVATION_QUEUE_TEMPLATE.format(
                    telegram_id=message['telegram_id']
                )
            )
