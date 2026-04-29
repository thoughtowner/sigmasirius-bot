from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context

from consumers.application_form_consumer.logger import correlation_id_ctx

from config.settings import settings
from src.schema.add_aplication_form.add_application_form import AddApplicationFormMessage
from src.states.add_application_form import AddApplicationForm
from ..router import router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.validators.add_application_form.validators import TitleValidator, DescriptionValidator
from src.validators.add_application_form import errors as validation
from src.messages import add_application_form as msg
from src.commands import ADD_APPLICATION_FORM
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio

from src.files_storage.storage_client import images_storage
import io

from uuid import uuid4

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
    # delete bot prompt (if present)
    try:
        for mid in ids:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass
    finally:
        # clear tracking
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


@router.message(F.text == ADD_APPLICATION_FORM)
async def start_add_application_form(message: Message, state: FSMContext):
    # user starts a new command -> clear old reservation inline markups
    try:
        from consumers.start_consumer.handlers.start import clear_reservation_markups
        await clear_reservation_markups(message.from_user.id)
    except Exception:
        pass
    await state.update_data(telegram_id=message.from_user.id)
    # track initiating command message so it can be deleted later
    await _append_message_id(state, message)
    await state.set_state(AddApplicationForm.title)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
    m = await message.answer(msg.ENTER_TITLE, reply_markup=kb)
    await _append_message_id(state, m)
    try:
        await state.update_data(last_question_message_id=m.message_id)
    except Exception:
        pass


@router.callback_query(F.data == 'start_cmd:add_application_form')
async def start_add_application_form_via_button(query: CallbackQuery, state: FSMContext):
    await query.answer()
    # user starts a new command via start keyboard button -> clear old reservation inline markups
    try:
        from consumers.start_consumer.handlers.start import clear_reservation_markups
        await clear_reservation_markups(query.from_user.id)
    except Exception:
        pass

    try:
        await query.message.delete()
    except Exception:
        pass
    await state.update_data(telegram_id=query.from_user.id)
    # track the inline starter message
    await _append_message_id(state, query.message)
    await state.set_state(AddApplicationForm.title)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
    m = await query.message.answer(msg.ENTER_TITLE, reply_markup=kb)
    await _append_message_id(state, m)
    try:
        await state.update_data(last_question_message_id=m.message_id)
    except Exception:
        pass


@router.message(AddApplicationForm.title)
async def enter_title(message: Message, state: FSMContext):
    # record user's reply
    await _append_message_id(state, message)
    try:
        await _remove_last_question_markup(state, message.bot, message.from_user.id)
    except Exception:
        pass

    # Allow typed cancel
    if message.text == 'Отмена':
            # delete tracked messages on cancel; then clear state
        await _delete_tracked_messages(state, message.bot, message.from_user.id)
        await state.clear()
        return

    answer = msg.ENTER_DESCRIPTION
    try:
        title = TitleValidator().validate(message)
        await state.update_data(title=title)
        await state.set_state(AddApplicationForm.description)
    except validation.TooLongTitleError:
        answer = msg.TOO_LONG_TITLE
    finally:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Пропустить', callback_data='skip_description'), InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
        m = await message.answer(answer, reply_markup=kb)
        await _append_message_id(state, m)
        try:
            await state.update_data(last_question_message_id=m.message_id)
        except Exception:
            pass


@router.message(AddApplicationForm.description)
async def enter_description(message: Message, state: FSMContext):
    # record user's reply
    await _append_message_id(state, message)

    # Allow typed cancel
    if message.text == 'Отмена':
            # delete tracked messages on cancel; then clear state
        await _delete_tracked_messages(state, message.bot, message.from_user.id)
        await state.clear()
        return

    if message.text == 'Пропустить':
        await state.update_data(description='')
        await state.set_state(AddApplicationForm.photo)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Пропустить', callback_data='skip_photo'), InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
        m = await message.answer(msg.UPLOAD_PHOTO, reply_markup=kb)
        await _append_message_id(state, m)
        try:
            await state.update_data(last_question_message_id=m.message_id)
        except Exception:
            pass
        return

    answer = msg.UPLOAD_PHOTO
    try:
        description = DescriptionValidator().validate(message)
        await state.update_data(description=description)
        await state.set_state(AddApplicationForm.photo)
    except validation.TooLongDescriptionError:
        answer = msg.TOO_LONG_DESCRIPTION
    finally:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Пропустить', callback_data='skip_photo'), InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
        m = await message.answer(answer, reply_markup=kb)
        await _append_message_id(state, m)


@router.message(AddApplicationForm.photo)
async def upload_photo(message: Message, state: FSMContext):
    from src.bot import bot
    # record user's reply (photo message)
    await _append_message_id(state, message)

    # Allow typed cancel
    if message.text == 'Отмена':
            # do not delete messages on cancel; just clear state
        await state.clear()
        return

    # If user typed 'Пропустить' (text), handle here
    if message.text == 'Пропустить':
        data = await state.get_data()
        m = await message.answer(msg.PUSH_DATA_TO_ADD_APPLICATION_FORM_QUERY)
        await _append_message_id(state, m)

        # delete tracked messages (question + replies)
        await _delete_tracked_messages(state, message.bot, message.from_user.id)
        state_data = await state.get_data()
        await state.clear()
        await state.update_data(state_data)

        application_form_message = AddApplicationFormMessage(
            event='add_application_form',
            telegram_id=data['telegram_id'],
            title=data['title'],
            description=data.get('description', ''),
            photo_title='',
            status='not_completed',
            is_test_data=False
        )

        async with channel_pool.acquire() as channel:
            logger.info('Send data to application_form queue...')
            application_form_exchange = await channel.declare_exchange(settings.APPLICATION_FORM_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            application_form_queue = await channel.declare_queue(settings.APPLICATION_FORM_QUEUE_NAME, durable=True)
            await application_form_queue.bind(application_form_exchange, settings.APPLICATION_FORM_QUEUE_NAME)

            await application_form_exchange.publish(
                aio_pika.Message(
                    msgpack.packb(application_form_message),
                ),
                settings.APPLICATION_FORM_QUEUE_NAME
            )
        # show start inline keyboard to user after creating application
        try:
            from consumers.start_consumer.handlers.start import send_reply_start_keyboard
            await send_reply_start_keyboard(message.from_user.id)
        except Exception:
            pass
        return

    # Otherwise expect a photo
    try:
        downloaded_photo_bytes_io = await bot.download(file=message.photo[-1].file_id)
        downloaded_photo_bytes_io.seek(0)
    except Exception:
        await message.answer(msg.INVALID_PHOTO)
        return

    photo_title = str(uuid4())
    images_storage.upload_file(photo_title, downloaded_photo_bytes_io)

    await state.update_data(photo_title=photo_title)

    data = await state.get_data()
    m = await message.answer(msg.PUSH_DATA_TO_ADD_APPLICATION_FORM_QUERY)
    await _append_message_id(state, m)

    # delete tracked messages (question + replies)
    await _delete_tracked_messages(state, message.bot, message.from_user.id)
    state_data = await state.get_data()
    await state.clear()
    await state.update_data(state_data)

    application_form_message = AddApplicationFormMessage(
        event='add_application_form',
        telegram_id=data['telegram_id'],
        title=data['title'],
        description=data.get('description', ''),
        photo_title=data['photo_title'],
        status='not_completed',
        is_test_data=False
    )

    async with channel_pool.acquire() as channel:
        logger.info('Send data to application_form queue...')
        application_form_exchange = await channel.declare_exchange(settings.APPLICATION_FORM_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        application_form_queue = await channel.declare_queue(settings.APPLICATION_FORM_QUEUE_NAME, durable=True)
        await application_form_queue.bind(application_form_exchange, settings.APPLICATION_FORM_QUEUE_NAME)

        await application_form_exchange.publish(
            aio_pika.Message(
                msgpack.packb(application_form_message),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.APPLICATION_FORM_QUEUE_NAME
        )
    # show start inline keyboard to user after creating application (photo case)
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(message.from_user.id)
    except Exception:
        pass


@router.callback_query(F.data.in_(['cancel_state', 'skip_description', 'skip_photo']))
async def handle_inline_callbacks(query: CallbackQuery, state: FSMContext):
    data = query.data
    chat_id = query.message.chat.id
    bot = query.bot

    if data == 'cancel_state':
        await query.answer()
        # delete tracked messages (bot prompts and user replies)
        try:
            # delete the inline message that contains the button
            try:
                await query.message.delete()
            except Exception:
                pass
                pass
        finally:
            # remove tracked messages and clear state; show selection reply keyboard
            await _delete_tracked_messages(state, query.bot, query.from_user.id)
            await state.clear()
            try:
                from consumers.start_consumer.handlers.start import send_reply_start_keyboard
                await send_reply_start_keyboard(query.from_user.id)
            except Exception:
                pass
        return

    if data == 'skip_description':
        await query.answer()
        await state.update_data(description='')
        await state.set_state(AddApplicationForm.photo)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Пропустить', callback_data='skip_photo'), InlineKeyboardButton(text='Отменить', callback_data='cancel_state')]])
        try:
            m = await query.message.answer(msg.UPLOAD_PHOTO, reply_markup=kb)
            await _append_message_id(state, m)
        except Exception:
            pass
        return

    if data == 'skip_photo':
        await query.answer()
        data_state = await state.get_data()
        try:
            await query.message.delete()
        except Exception:
            pass
        m = await query.message.answer(msg.PUSH_DATA_TO_ADD_APPLICATION_FORM_QUERY)
        await _append_message_id(state, m)

        # delete all tracked messages (including the initiating command)
        await _delete_tracked_messages(state, query.bot, query.from_user.id)
        state_data = await state.get_data()
        await state.clear()
        await state.update_data(state_data)

        application_form_message = AddApplicationFormMessage(
            event='add_application_form',
            telegram_id=data_state['telegram_id'],
            title=data_state['title'],
            description=data_state.get('description', ''),
            photo_title='',
            status='not_completed',
            is_test_data=False
        )

        async with channel_pool.acquire() as channel:
            logger.info('Send data to application_form queue...')
            application_form_exchange = await channel.declare_exchange(settings.APPLICATION_FORM_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            application_form_queue = await channel.declare_queue(settings.APPLICATION_FORM_QUEUE_NAME, durable=True)
            await application_form_queue.bind(application_form_exchange, settings.APPLICATION_FORM_QUEUE_NAME)

            await application_form_exchange.publish(
                aio_pika.Message(
                    msgpack.packb(application_form_message),
                ),
                settings.APPLICATION_FORM_QUEUE_NAME
            )
        # show start inline keyboard to user after creating application
        try:
            from consumers.start_consumer.handlers.start import send_reply_start_keyboard
            await send_reply_start_keyboard(query.from_user.id)
        except Exception:
            pass
        return
        return
