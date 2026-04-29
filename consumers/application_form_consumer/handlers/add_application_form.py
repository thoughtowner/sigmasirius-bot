from ..mappers import get_user, get_application_form
from config.settings import settings
from ..parsers import parse_status
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm, ApplicationFormStatus
from sqlalchemy import insert, select

from ..schema.application_form_for_repairman import ApplicationFormForRepairmanMessage
from ..schema.application_form_for_resident import ApplicationFormForResidentMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.msg_templates.env import render

import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool
from src.storage.redis import redis_storage
import json


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_add_application_form_event(message): # TODO async def handle_application_form_event(message: ApplicationFormMessage)
    async with async_session() as db:
        user_result = await db.execute(select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

        application_form_query = insert(ApplicationForm).values(
            title=message['title'],
            description=message['description'],
            status=ApplicationFormStatus(message['status']),
            user_id=user_id
        ).returning(ApplicationForm.id)
        application_form_result = await db.execute(application_form_query)
        application_form_id = application_form_result.scalar()

        await db.commit()

        application_form_for_repairman_query = (
            select(
                User.full_name,
                User.phone_number,
                ApplicationForm.title,
                ApplicationForm.description,
                ApplicationForm.status
            )
            .select_from(User)
            .join(ApplicationForm, ApplicationForm.user_id == User.id)
            .where(ApplicationForm.id == application_form_id)
        )
        application_form_for_repairman_result = await db.execute(application_form_for_repairman_query)
        application_form_for_repairman = application_form_for_repairman_result.fetchone()

        parsed_application_form_for_repairman = ApplicationFormForRepairmanMessage(
            resident_full_name=application_form_for_repairman[0],
            resident_phone_number=application_form_for_repairman[1],
            title=application_form_for_repairman[2],
            description=application_form_for_repairman[3],
            status=parse_status(application_form_for_repairman[4].value)
        )

        parsed_application_form_for_resident = ApplicationFormForResidentMessage(
            title=application_form_for_repairman[2],
            description=application_form_for_repairman[3],
            status=parse_status(application_form_for_repairman[4].value)
        )

        repairmen_telegram_id_query = await db.execute(
            select(User.telegram_id).filter(User.is_repairman == True)
        )
        repairmen_telegram_id = repairmen_telegram_id_query.scalars().all()

        photo_input_file = None
        if message.get('photo_title'):
            try:
                fetched = images_storage.get_file(message['photo_title'])
                if fetched:
                    photo_input_file = BufferedInputFile(fetched, message['photo_title'])
            except Exception:
                photo_input_file = None

        take_for_processing_btn = InlineKeyboardButton(text='Взять в обработку', callback_data='take_application_form_for_processing')
        cancel_btn = InlineKeyboardButton(text='Отменить', callback_data='cancel_application_form')
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[take_for_processing_btn], [cancel_btn]]
        )

        for repairman_telegram_id in repairmen_telegram_id:
            if photo_input_file:
                application_form_for_repairman_message = await bot.send_photo(
                    photo=photo_input_file,
                    caption=render(
                        'application_form/application_form_for_repairman.jinja2',
                        body=parsed_application_form_for_repairman
                    ),
                    reply_markup=markup,
                    chat_id=repairman_telegram_id
                )
            else:
                application_form_for_repairman_message = await bot.send_message(
                    chat_id=repairman_telegram_id,
                    text=render('application_form/application_form_for_repairman.jinja2', body=parsed_application_form_for_repairman),
                    reply_markup=markup
                )

            # store mapping in redis: add to application_form:{id}:members and reverse map
            member = {'telegram_id': repairman_telegram_id, 'message_id': application_form_for_repairman_message.message_id}
            key = f'application_form:{str(application_form_id)}:members'
            current_raw = await redis_storage.get(key)
            if current_raw:
                try:
                    current = json.loads(current_raw)
                except Exception:
                    current = []
            else:
                current = []
            current.append(member)
            await redis_storage.set(key, json.dumps(current))
            # reverse lookup
            await redis_storage.set(f'message_map:{repairman_telegram_id}:{application_form_for_repairman_message.message_id}', str(application_form_id))

        # For resident, attach an inline 'Отменить' button only when application is not_completed
        # Use the original incoming message status (message['status']) which is the canonical value
        resident_reply_markup = None
        try:
            incoming_status = message.get('status') if isinstance(message, dict) else None
        except Exception:
            incoming_status = None

        if incoming_status == 'not_completed':
            resident_cancel_btn = InlineKeyboardButton(text='Отменить', callback_data='resident_cancel_application')
            resident_reply_markup = InlineKeyboardMarkup(inline_keyboard=[[resident_cancel_btn]])

        if photo_input_file:
            application_form_for_resident_message = await bot.send_photo(
                photo=photo_input_file,
                caption=render(
                    'application_form/application_form_for_resident.jinja2',
                    body=parsed_application_form_for_resident
                ),
                chat_id=message['telegram_id'],
                reply_markup=resident_reply_markup
            )
        else:
            application_form_for_resident_message = await bot.send_message(
                chat_id=message['telegram_id'],
                text=render('application_form/application_form_for_resident.jinja2', body=parsed_application_form_for_resident),
                reply_markup=resident_reply_markup
            )
        # store resident mapping in redis as well
        resident_member = {'telegram_id': message['telegram_id'], 'message_id': application_form_for_resident_message.message_id}
        key = f'application_form:{str(application_form_id)}:members'
        current_raw = await redis_storage.get(key)
        if current_raw:
            try:
                current = json.loads(current_raw)
            except Exception:
                current = []
        else:
            current = []
        current.append(resident_member)
        await redis_storage.set(key, json.dumps(current))
        await redis_storage.set(f'message_map:{message["telegram_id"]}:{application_form_for_resident_message.message_id}', str(application_form_id))
        # store owner quick lookup to allow resident to cancel their last application
        try:
            await redis_storage.set(f'application_form_owner:{message["telegram_id"]}', str(application_form_id))
        except Exception:
            pass

        await db.commit()
