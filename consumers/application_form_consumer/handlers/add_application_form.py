from ..mappers import get_user, get_application_form
from config.settings import settings
from ..parsers import parse_status
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm, TelegramIdAndMessageId
from sqlalchemy import insert, select

from ..schema.application_form_for_repairman import ApplicationFormForRepairmanMessage
from ..schema.application_form_for_resident import ApplicationFormForResidentMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_add_application_form_event(message): # TODO async def handle_application_form_event(message: ApplicationFormMessage)
    async with async_session() as db:
        user_result = await db.execute(select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

        application_form_query = insert(ApplicationForm).values(
            title=message['title'],
            description=message['description'],
            status=ApplicationForm.Status(message['status']),
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
            title=application_form_for_repairman[3],
            description=application_form_for_repairman[4],
            status=parse_status(application_form_for_repairman[5].value)
        )

        repairmen_telegram_id_query = await db.execute(
            select(User.telegram_id).filter(User.is_repairman == True)
        )
        repairmen_telegram_id = repairmen_telegram_id_query.scalars().all()

        photo_input_file = BufferedInputFile(images_storage.get_file(message['photo_title']), message['photo_title'])

        take_for_processing_btn = InlineKeyboardButton(text='Взять в обработку', callback_data='take_application_form_for_processing')
        cancel_btn = InlineKeyboardButton(text='Отменить', callback_data='cancel_application_form')
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[take_for_processing_btn], [cancel_btn]]
        )

        for repairman_telegram_id in repairmen_telegram_id:
            application_form_for_repairman_message = await bot.send_photo(
                photo=photo_input_file,
                caption=render(
                    'application_form/application_form_for_repairman.jinja2',
                    body=parsed_application_form_for_repairman
                ),
                reply_markup=markup,
                chat_id=repairman_telegram_id
            )

            await db.execute(insert(TelegramIdAndMessageId).values(
                telegram_id=repairman_telegram_id,
                message_id=application_form_for_repairman_message.message_id,
                application_form_id=application_form_id
            ))

            await db.flush()

        application_form_for_resident_message = await bot.send_photo(
            photo=photo_input_file,
            caption=render(
                'application_form/application_form_for_resident.jinja2',
                body=parsed_application_form_for_resident
            ),
            chat_id=message['telegram_id']
        )

        await db.execute(insert(TelegramIdAndMessageId).values(
            telegram_id=message['telegram_id'],
            message_id=application_form_for_resident_message.message_id,
            application_form_id=application_form_id
        ))

        await db.commit()
