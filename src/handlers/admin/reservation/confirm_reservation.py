from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context
from consumers.reservation_consumer.logger import correlation_id_ctx

from config.settings import settings
from src.schema.reservation.check_unconfirmed_reservation import CheckUnconfirmedReservationMessage
from src.states.reservation import Reservation as ReservationState
from ..router import router
from src.keyboard_buttons.reservation import ROOM_CLASSES_ROW_BUTTONS, CHECK_RESERVATION_DATA_ROW_BUTTONS
from aiogram.types import ReplyKeyboardRemove
from src.messages import reservation as msg
from src.validators.create_reservation.validators import PeopleNumberValidator
from src.validators.create_reservation import errors as validation
from src.keyboard_buttons.texts import ROOM_CLASSES, CHECK_RESERVATION_DATA_ANSWERS
from src.commands import CONFIRM_RESERVATION
from src.validators.start.validators import PhoneNumberValidator
from src.validators.start import errors as validation
from src.logger import LOGGING_CONFIG, logger
import logging.config
from src.msg_templates.env import render
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.storage.db import async_session
from src.model.models import Room, Reservation, ReservationStatus, User
from sqlalchemy import select, and_, or_
from datetime import datetime, date
import aio_pika
import msgpack
import asyncio
import json
from uuid import uuid4
from src.storage.redis import redis_storage

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == CONFIRM_RESERVATION)
async def start_confirm_reservation(message: Message, state: FSMContext):
    await state.set_state(ReservationState.phone_number)
    await message.answer('Введите номер телефона клиента в формате +79991234567')


@router.message(ReservationState.phone_number)
async def handle_admin_phone(message: Message, state: FSMContext):
    admin_id = message.from_user.id

    try:
        phone_number = PhoneNumberValidator().validate(message)
        await state.update_data(phone_number=phone_number)
    except validation.InvalidPhoneNumberFormatError:
        await message.answer(msg.INVALID_PHONE_NUMBER_FORMAT)
        return

    check_msg = CheckUnconfirmedReservationMessage(event='check_unconfirmed_reservation', phone_number=phone_number, telegram_id=admin_id)

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb(check_msg)),
            settings.RESERVATION_QUEUE_NAME
        )

    # wait for response on admin queue
    async with channel_pool.acquire() as channel:
        user_reservation_queue = await channel.declare_queue(
            settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=admin_id),
            durable=True,
        )

        retries = 100
        body = None
        for _ in range(retries):
            try:
                reservation_response_message = await user_reservation_queue.get(no_ack=True)
                body = msgpack.unpackb(reservation_response_message.body)
                break
            except Exception:
                await asyncio.sleep(1)

    if not body or not body.get('found'):
        await message.answer('Не найдено неподтверждённых броней по этому номеру или бронь не на сегодня.')
        return
    
    state_data = await state.get_data()
    await state.clear()
    await state.update_data(state_data)

    reservation = body['reservation']
    res_text = (
        f"Бронь ID: {reservation['id']}\n"
        f"Клиент: {phone_number}\n"
        f"Количество человек: {reservation['people_quantity']}\n"
        f"Класс номера: {reservation['room_class']}\n"
        f"Дата заезда: {reservation['check_in_date']}\n"
        f"Дата выезда: {reservation['eviction_date']}\n"
    )

    pick_btn = InlineKeyboardButton(text='Подобрать номер', callback_data=f'pick_room:{reservation["id"]}')
    kb = InlineKeyboardMarkup(inline_keyboard=[[pick_btn]])
    await message.answer(res_text, reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith('pick_room:'))
async def handle_pick_room_cb(query):
    _, reservation_id = query.data.split(':', 1)
    admin_id = query.from_user.id

    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'pick_room',
                'reservation_id': reservation_id,
                'telegram_id': admin_id,
                'callback_query_message_id': query.message.message_id,
                'callback_chat_id': query.message.chat.id,
            })),
            settings.RESERVATION_QUEUE_NAME
        )

    await query.answer('Запрос отправлен на сервер, подождите...')


@router.callback_query(lambda c: c.data and c.data.startswith('assign_room:'))
async def handle_assign_room_cb(query):
    _, token = query.data.split(':', 1)
    admin_id = query.from_user.id

    # forward assign request to reservation consumer
    async with channel_pool.acquire() as channel:
        reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        await reservation_exchange.publish(
            aio_pika.Message(msgpack.packb({
                'event': 'assign_room',
                'token': token,
                'telegram_id': admin_id,
                'callback_chat_id': query.message.chat.id,
                'callback_message_id': query.message.message_id,
            })),
            settings.RESERVATION_QUEUE_NAME
        )

    await query.answer('Запрос на привязку номера отправлен серверу')