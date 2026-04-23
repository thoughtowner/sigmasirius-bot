from ..mappers import get_user, get_application_form
from config.settings import settings
from ..parsers import parse_status
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm, ApplicationFormStatus
from sqlalchemy import insert, select, update, and_

from ..schema.application_form_for_repairman import ApplicationFormForRepairmanMessage
from ..schema.application_form_for_resident import ApplicationFormForResidentMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.msg_templates.env import render

import io
from src.files_storage.storage_client import images_storage
from src.storage.redis import redis_storage
import json

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_change_application_form_status_event(message): # TODO async def handle_application_form_event(message: ApplicationFormStatusMessage)
    if message['action'] == 'take_application_form_for_processing':
        async with (async_session() as db):
            new_status = ApplicationFormStatus(message['new_status'])

            # find application_form_id via redis reverse map
            application_form_id = None
            try:
                mapping = await redis_storage.get(f"message_map:{message['working_repairman_telegram_id']}:{message['working_repairman_message_id']}")
                if mapping:
                    application_form_id = mapping.decode() if isinstance(mapping, bytes) else mapping
            except Exception:
                application_form_id = None

            if not application_form_id:
                logger.warning('No redis mapping for message_map:%s:%s', message['working_repairman_telegram_id'], message['working_repairman_message_id'])
                return

            await db.execute(
                update(ApplicationForm).
                where(ApplicationForm.id == application_form_id).
                values(status=new_status)
            )
            await db.commit()

            application_form_for_repairman_query = await db.execute(
                select(
                    User.full_name,
                    User.phone_number,
                    ApplicationForm.title,
                    ApplicationForm.description,
                    ApplicationForm.status
                )
                .select_from(User)
                .join(ApplicationForm, ApplicationForm.user_id == User.id)
            # ApplicationForm.status is stored as Enum on the ApplicationForm table
                .where(ApplicationForm.id == application_form_id)
            )
            application_form_for_repairman = application_form_for_repairman_query.fetchone()

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

            # load members list from redis
            members = []
            try:
                raw = await redis_storage.get(f"application_form:{str(application_form_id)}:members")
                if raw:
                    members = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            except Exception:
                members = []

            parsed_resident_telegram_id_and_message_id = None
            for m in members:
                if int(m.get('telegram_id')) == int(message.get('working_repairman_telegram_id')) and int(m.get('message_id')) == int(message.get('working_repairman_message_id')):
                    # this is the working repairman's own message; skip for resident mapping
                    continue
                # find resident mapping by checking ownership later; for now collect members
            # Try to find resident: owner is user of ApplicationForm in DB
            resident_mapping = None
            try:
                # fetch app owner from DB
                app_owner_q = await db.execute(select(ApplicationForm.user_id).filter(ApplicationForm.id == application_form_id))
                owner_id = app_owner_q.scalar()
                if owner_id:
                    # find member whose telegram_id maps to that owner user
                    # load user.telegram_id
                    user_q = await db.execute(select(User.telegram_id).filter(User.id == owner_id))
                    owner_telegram = user_q.scalar()
                    if owner_telegram:
                        for m in members:
                            if int(m.get('telegram_id')) == int(owner_telegram):
                                resident_mapping = {'telegram_id': m.get('telegram_id'), 'message_id': m.get('message_id')}
                                break
            except Exception:
                resident_mapping = None

            for member in members:
                member_telegram = member.get('telegram_id')
                member_message = member.get('message_id')
                if int(member_telegram) == int(message['working_repairman_telegram_id']) \
                        and int(member_message) == int(message['working_repairman_message_id']):
                    await bot.edit_message_caption(
                        caption=render(
                            'application_form/application_form_for_repairman.jinja2',
                            body=parsed_application_form_for_repairman
                        ),
                        chat_id=member_telegram,
                        message_id=member_message
                    )

                    complete_btn = InlineKeyboardButton(text='Выполнить', callback_data='complete_application_form')
                    new_markup = InlineKeyboardMarkup(
                        inline_keyboard=[[complete_btn]]
                    )

                    await bot.edit_message_reply_markup(
                        reply_markup=new_markup,
                        chat_id=member_telegram,
                        message_id=member_message
                    )
                elif resident_mapping and int(member.get('telegram_id')) == int(resident_mapping['telegram_id']) \
                        and int(member.get('message_id')) == int(resident_mapping['message_id']):
                    await bot.edit_message_caption(
                        caption=render(
                            'application_form/application_form_for_resident.jinja2',
                            body=parsed_application_form_for_resident
                        ),
                        chat_id=resident_mapping['telegram_id'],
                        message_id=resident_mapping['message_id']
                    )
                else:
                    await bot.delete_message(
                        chat_id=member_telegram,
                        message_id=member_message
                    )

    elif message['action'] == 'complete_application_form':
        async with async_session() as db:
            new_status = ApplicationFormStatus(message['new_status'])

            # find application_form via redis
            application_form_id = None
            try:
                mapping = await redis_storage.get(f"message_map:{message['working_repairman_telegram_id']}:{message['working_repairman_message_id']}")
                if mapping:
                    application_form_id = mapping.decode() if isinstance(mapping, bytes) else mapping
            except Exception:
                application_form_id = None

            if not application_form_id:
                logger.warning('No redis mapping for message_map:%s:%s', message['working_repairman_telegram_id'], message['working_repairman_message_id'])
                return

            await db.execute(
                update(ApplicationForm).
                where(ApplicationForm.id == application_form_id).
                values(status=new_status)
            )
            await db.commit()

            application_form_for_resident_query = await db.execute(
                select(
                    ApplicationForm.title,
                    ApplicationForm.description,
                    ApplicationForm.status
                )
                .where(ApplicationForm.id == application_form_id)
            )
            application_form_for_resident = application_form_for_resident_query.fetchone()

            parsed_application_form_for_resident = ApplicationFormForResidentMessage(
                title=application_form_for_resident[0],
                description=application_form_for_resident[1],
                status=parse_status(application_form_for_resident[2].value)
            )

            # load members and resident mapping from redis
            members = []
            try:
                raw = await redis_storage.get(f"application_form:{str(application_form_id)}:members")
                if raw:
                    members = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            except Exception:
                members = []

            resident_mapping = None
            try:
                app_owner_q = await db.execute(select(ApplicationForm.user_id).filter(ApplicationForm.id == application_form_id))
                owner_id = app_owner_q.scalar()
                if owner_id:
                    user_q = await db.execute(select(User.telegram_id).filter(User.id == owner_id))
                    owner_telegram = user_q.scalar()
                    if owner_telegram:
                        for m in members:
                            if int(m.get('telegram_id')) == int(owner_telegram):
                                resident_mapping = {'telegram_id': m.get('telegram_id'), 'message_id': m.get('message_id')}
                                break
            except Exception:
                resident_mapping = None

            await bot.delete_message(
                chat_id=message['working_repairman_telegram_id'],
                message_id=message['working_repairman_message_id']
            )

            if resident_mapping:
                await bot.edit_message_caption(
                    caption=render(
                        'application_form/application_form_for_resident.jinja2',
                        body=parsed_application_form_for_resident
                    ),
                    chat_id=resident_mapping['telegram_id'],
                    message_id=resident_mapping['message_id']
                )

    elif message['action'] == 'cancel_application_form':
        async with async_session() as db:
            new_status = ApplicationFormStatus(message['new_status'])

            application_form_id_result = await db.execute(
                select(TelegramIdAndMessageId.application_form_id).filter(and_(
                    TelegramIdAndMessageId.telegram_id == message['working_repairman_telegram_id'],
                    TelegramIdAndMessageId.message_id == message['working_repairman_message_id']
                ))
            )
            application_form_id = application_form_id_result.scalar()

            await db.execute(
                update(ApplicationForm).
                where(ApplicationForm.id == application_form_id).
                values(status=new_status)
            )
            await db.commit()

            application_form_for_resident_query = await db.execute(
                select(
                    ApplicationForm.title,
                    ApplicationForm.description,
                    ApplicationForm.status
                )
                .where(ApplicationForm.id == application_form_id)
            )
            application_form_for_resident = application_form_for_resident_query.fetchone()

            parsed_application_form_for_resident = ApplicationFormForResidentMessage(
                title=application_form_for_resident[0],
                description=application_form_for_resident[1],
                status=parse_status(application_form_for_resident[2].value)
            )

            # load members list from redis and find resident mapping by owner
            members = []
            try:
                raw = await redis_storage.get(f"application_form:{str(application_form_id)}:members")
                if raw:
                    members = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            except Exception:
                members = []

            parsed_resident_telegram_id_and_message_id = None
            try:
                app_owner_q = await db.execute(select(ApplicationForm.user_id).filter(ApplicationForm.id == application_form_id))
                owner_id = app_owner_q.scalar()
                if owner_id:
                    user_q = await db.execute(select(User.telegram_id).filter(User.id == owner_id))
                    owner_telegram = user_q.scalar()
                    if owner_telegram:
                        for m in members:
                            if int(m.get('telegram_id')) == int(owner_telegram) and int(m.get('message_id')) != int(message['working_repairman_message_id']):
                                parsed_resident_telegram_id_and_message_id = {'telegram_id': m.get('telegram_id'), 'message_id': m.get('message_id')}
                                break
            except Exception:
                parsed_resident_telegram_id_and_message_id = None

            await bot.delete_message(
                chat_id=message['working_repairman_telegram_id'],
                message_id=message['working_repairman_message_id']
            )

            if parsed_resident_telegram_id_and_message_id:
                await bot.edit_message_caption(
                    caption=render(
                        'application_form/application_form_for_resident.jinja2',
                        body=parsed_application_form_for_resident
                    ),
                    chat_id=parsed_resident_telegram_id_and_message_id['telegram_id'],
                    message_id=parsed_resident_telegram_id_and_message_id['message_id']
                )
