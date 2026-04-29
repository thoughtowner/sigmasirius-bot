from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context
from sqlalchemy import select
from src.storage.db import async_session

from src.states.start import Start
from config.settings import settings
from src.schema.start.start import StartMessage
from src.schema.start.check_start import CheckStartMessage
from src.schema.start.check_phone_number import CheckPhoneNumberMessage
from ..router import router
from src.messages import start as msg
from src.commands import START
from src.validators.start.validators import PhoneNumberValidator, FullNameValidator
from src.validators.start import errors as validation
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)


async def _append_message_id(state: FSMContext, msg):
    try:
        data = await state.get_data()
    except Exception:
        data = {}
    ids = data.get('message_ids', []) or []
    mid = getattr(msg, 'message_id', None)
    if mid is None:
        try:
            mid = msg.message_id
        except Exception:
            mid = None
    if mid:
        ids.append(mid)
        await state.update_data(message_ids=ids)


async def _delete_tracked_messages(state: FSMContext, bot, chat_id):
    data = await state.get_data() or {}
    ids = data.get('message_ids', []) or []
    try:
        for mid in ids:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass
    finally:
        try:
            await state.update_data(message_ids=[])
        except Exception:
            pass


async def _remove_last_question_markup(state: FSMContext, bot, chat_id):
    try:
        data = await state.get_data() or {}
    except Exception:
        data = {}
    mid = data.get('last_question_message_id')
    if not mid:
        return
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=int(mid), reply_markup=None)
    except Exception:
        pass
    try:
        await state.update_data(last_question_message_id=None)
    except Exception:
        pass

@router.message(F.text == START)
async def check_start(message: Message, state: FSMContext):
    await state.update_data(telegram_id=message.from_user.id)
    # track the initiating command message so it can be deleted later
    await _append_message_id(state, message)

    data = await state.get_data()
    check_start_message = CheckStartMessage(
        event='check_start',
        telegram_id=data['telegram_id'],
        is_test_data=False,
    )

    async with channel_pool.acquire() as channel:
        logger.info('Send data to start queue for check start status...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(check_start_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.START_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:
        reverse_start_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(
                telegram_id=message.from_user.id
            ),
            durable=True,
        )

        retries = 10
        for _ in range(retries):
            try:
                start_response_message = await reverse_start_queue.get(no_ack=True)
                body = msgpack.unpackb(start_response_message.body)
                break
            except QueueEmpty:
                await asyncio.sleep(1)

        # if not body:
        #     state_data = await state.get_data()
        #     await state.clear()
        #     await state.update_data(state_data)
        #     return
        await state.update_data(flag=body['flag'])
        if body['flag']:
            await state.set_state(Start.full_name)
            # offer inline button to use Telegram-linked phone and inline cancel
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Отменить', callback_data='cancel_state')],
            ])
            m = await message.answer(msg.ENTER_FULL_NAME, reply_markup=kb)
            await _append_message_id(state, m)
            try:
                await state.update_data(last_question_message_id=m.message_id)
            except Exception:
                pass
        else:
            # await message.answer(msg.WELCOME_BACK)

            state_data = await state.get_data()
            await state.clear()
            await state.update_data(state_data)

            start_message = StartMessage(
                event='start',
                telegram_id=state_data['telegram_id'],
                full_name="null",
                phone_number="null",
                # flag=state_data['flag']
                is_test_data=False,
            )

            async with channel_pool.acquire() as channel:
                logger.info('Send data to start queue...')
                start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
                start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
                await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

                await start_exchange.publish(
                    aio_pika.Message(
                        msgpack.packb(start_message),
                        # correlation_id=correlation_id_ctx.get()
                    ),
                    settings.START_QUEUE_NAME
                )


@router.callback_query(F.data == 'start_cmd:start')
async def start_via_button(query: CallbackQuery, state: FSMContext):
    await query.answer()
    # remove the inline starter message
    try:
        await query.message.delete()
    except Exception:
        pass

    await state.update_data(telegram_id=query.from_user.id)

    data = await state.get_data()
    check_start_message = CheckStartMessage(
        event='check_start',
        telegram_id=data['telegram_id'],
        is_test_data=False,
    )

    async with channel_pool.acquire() as channel:
        logger.info('Send data to start queue for check start status (via button)...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(check_start_message),
            ),
            settings.START_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:
        reverse_start_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(
                telegram_id=query.from_user.id
            ),
            durable=True,
        )

        retries = 10
        start_response_body = None
        for _ in range(retries):
            try:
                start_response_message = await reverse_start_queue.get(no_ack=True)
                start_response_body = msgpack.unpackb(start_response_message.body)
                break
            except QueueEmpty:
                await asyncio.sleep(1)

        if not start_response_body:
            return

        await state.update_data(flag=start_response_body['flag'])
        if start_response_body['flag']:
            await state.set_state(Start.full_name)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Отменить', callback_data='cancel_state')],
            ])
            m = await query.message.answer(msg.ENTER_FULL_NAME, reply_markup=kb)
            await _append_message_id(state, m)
            try:
                await state.update_data(last_question_message_id=m.message_id)
            except Exception:
                pass
        else:
            state_data = await state.get_data()
            await state.clear()
            await state.update_data(state_data)

            start_message = StartMessage(
                event='start',
                telegram_id=state_data['telegram_id'],
                full_name="null",
                phone_number="null",
                is_test_data=False,
            )

            async with channel_pool.acquire() as channel:
                logger.info('Send data to start queue (via button)...')
                start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
                start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
                await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

                await start_exchange.publish(
                    aio_pika.Message(
                        msgpack.packb(start_message),
                    ),
                    settings.START_QUEUE_NAME
                )




@router.message(Start.full_name)
async def enter_full_name(message: Message, state: FSMContext):
    # record user's reply
    await _append_message_id(state, message)
    try:
        await _remove_last_question_markup(state, message.bot, message.from_user.id)
    except Exception:
        pass
    # Allow typing cancel or use inline cancel button (callback handled elsewhere)
    if message.text == 'Отмена':
        # do not delete messages on cancel; just clear state
        await state.clear()
        return

    answer = msg.ENTER_PHONE_NUMBER
    try:
        full_name = FullNameValidator().validate(message)
        await state.update_data(full_name=full_name)
        await state.set_state(Start.phone_number)
    except validation.FullNameCannotContainMultipleSpacesError:
        answer = msg.FULL_NAME_CANNOT_CONTAIN_MULTIPLE_SPACES
    except validation.InvalidFullNameFormatError:
        answer = msg.INVALID_FULL_NAME_FORMAT
    except validation.NameShouldContainOnlyLettersError:
        answer = msg.NAME_SHOULD_CONTAIN_ONLY_LETTERS
    except validation.TooLongNameError:
        answer = msg.TOO_LONG_NAME
    except validation.TooShortNameError:
        answer = msg.TOO_SHORT_NAME
    except validation.NameBeginCannotBeLowercaseError:
        answer = msg.NAME_BEGIN_CANNOT_BE_LOWER
    finally:
        # send phone prompt with a reply-keyboard requesting contact (single-click)
        try:
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text='Использовать номер из Telegram', request_contact=True)],
                [KeyboardButton(text='Отмена')],
            ], resize_keyboard=True, one_time_keyboard=True)
        except Exception:
            kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Использовать номер из Telegram', request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)

        m = await message.answer(answer, reply_markup=kb)
        await _append_message_id(state, m)
        try:
            await state.update_data(last_question_message_id=m.message_id)
        except Exception:
            pass

@router.message(Start.phone_number)
async def enter_phone_number(message: Message, state: FSMContext):
    await _append_message_id(state, message)
    try:
        await _remove_last_question_markup(state, message.bot, message.from_user.id)
    except Exception:
        pass
    # handle contact share
    if getattr(message, 'contact', None):
        phone_number = message.contact.phone_number
        await state.update_data(phone_number=phone_number)
        # remove the reply keyboard asking for contact
        # try:
        #     await message.answer('Спасибо, номер получен.', reply_markup=ReplyKeyboardRemove())
        # except Exception:
        #     pass
    else:
        if message.text == 'Отмена':
            await _delete_tracked_messages(state, message.bot, message.from_user.id)
            await state.clear()
            return
        try:
            phone_number = PhoneNumberValidator().validate(message)
            await state.update_data(phone_number=phone_number)
        except validation.InvalidPhoneNumberFormatError:
            await message.answer(msg.INVALID_PHONE_NUMBER_FORMAT)
            return
    
    data = await state.get_data()
    check_phone_number_message = CheckPhoneNumberMessage(
        event='check_phone_number',
        telegram_id=data['telegram_id'],
        is_test_data=False,
        phone_number=phone_number
    )

    async with channel_pool.acquire() as channel:
        logger.info('Send data to start queue for check phone number status...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(check_phone_number_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.START_QUEUE_NAME
        )

    async with channel_pool.acquire() as channel:
        reverse_start_queue = await channel.declare_queue(
            settings.USER_CHECK_START_QUEUE_TEMPLATE.format(
                telegram_id=message.from_user.id
            ),
            durable=True,
        )

        retries = 10
        for _ in range(retries):
            try:
                check_phone_response_message = await reverse_start_queue.get(no_ack=True)
                body = msgpack.unpackb(check_phone_response_message.body)
                break
            except QueueEmpty:
                await asyncio.sleep(1)

        # if not body:
        #     state_data = await state.get_data()
        #     await state.clear()
        #     await state.update_data(state_data)
        #     return
        await state.update_data(flag=body['flag'])
        if not body['flag']:
            await message.answer('Этот номер телефона уже используется другим пользователем!')
            return
    
    state_data = await state.get_data()
    # delete question and user reply messages
    await _delete_tracked_messages(state, message.bot, message.from_user.id)
    await state.clear()
    await state.update_data(state_data)

    start_message = StartMessage(
        event='start',
        telegram_id=state_data['telegram_id'],
        full_name=state_data['full_name'],
        phone_number=state_data['phone_number'],
        # flag=state_data['flag']
        is_test_data=False,
    )

    async with channel_pool.acquire() as channel:
        logger.info('Send data to start queue...')
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        start_queue = await channel.declare_queue(settings.START_QUEUE_NAME, durable=True)
        await start_queue.bind(start_exchange, settings.START_QUEUE_NAME)

        await start_exchange.publish(
            aio_pika.Message(
                msgpack.packb(start_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.START_QUEUE_NAME
        )


@router.callback_query(F.data == 'cancel_state')
async def handle_cancel_state_callback(query, state: FSMContext):
    await query.answer()
    chat_id = query.message.chat.id
    bot = query.bot
    # delete tracked question and replies and clear state; do not send selection keyboard
    await _delete_tracked_messages(state, query.bot, query.from_user.id)
    await state.clear()
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(query.from_user.id)
    except Exception:
        pass



