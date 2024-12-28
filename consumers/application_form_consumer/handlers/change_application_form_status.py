from ..mappers import get_user, get_application_form
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, Role, ApplicationForm, ResidentAdditionalData, ApplicationFormStatus, UserRole, TelegramIdAndMessageId
from sqlalchemy import insert, select, update, and_

from ..schema.application_form_for_admin import ApplicationFormForAdminMessage
from ..schema.application_form_for_resident import ApplicationFormForResidentMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_change_application_form_status_event(message): # TODO async def handle_application_form_event(message: ApplicationFormStatusMessage)
    if message['action'] == 'take_application_form_for_processing':
        async with (async_session() as db):
            new_status_result = await db.execute(select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == message['new_status']))
            new_status_id = new_status_result.scalar()

            application_form_id_result = await db.execute(
                select(TelegramIdAndMessageId.application_form_id).filter(and_(
                    TelegramIdAndMessageId.telegram_id == message['working_admin_telegram_id'],
                    TelegramIdAndMessageId.message_id == message['working_admin_message_id']
                ))
            )
            application_form_id = application_form_id_result.scalar()

            await db.execute(
                update(ApplicationForm).
                where(ApplicationForm.id == application_form_id).
                values(status_id=new_status_id)
            )
            await db.commit()

            application_form_for_admin_query = await db.execute(
                select(
                    ResidentAdditionalData.full_name,
                    ResidentAdditionalData.phone_number,
                    ResidentAdditionalData.room,
                    ApplicationForm.title,
                    ApplicationForm.description,
                    ApplicationFormStatus.title
                )
                .select_from(User)
                .join(ResidentAdditionalData, ResidentAdditionalData.user_id == User.id)
                .join(ApplicationForm, ApplicationForm.user_id == User.id)
                .join(ApplicationFormStatus, ApplicationFormStatus.id == ApplicationForm.status_id)
                .where(ApplicationForm.id == application_form_id)
            )
            application_form_for_admin = application_form_for_admin_query.fetchone()

            parsed_application_form_for_admin = ApplicationFormForAdminMessage(
                resident_full_name=application_form_for_admin[0],
                resident_phone_number=application_form_for_admin[1],
                resident_room=application_form_for_admin[2],
                title=application_form_for_admin[3],
                description=application_form_for_admin[4],
                status=application_form_for_admin[5]
            )

            parsed_application_form_for_resident = ApplicationFormForResidentMessage(
                title=application_form_for_admin[3],
                description=application_form_for_admin[4],
                status=application_form_for_admin[5]
            )

            resident_telegram_id_and_message_id_query = await db.execute(
                select(
                    TelegramIdAndMessageId.telegram_id,
                    TelegramIdAndMessageId.message_id
                )
                .join(User, User.telegram_id == TelegramIdAndMessageId.telegram_id)
                .join(ApplicationForm, ApplicationForm.id == TelegramIdAndMessageId.application_form_id)
                .where(
                    (ApplicationForm.id == application_form_id)
                    & (User.id == ApplicationForm.user_id)
                    & (TelegramIdAndMessageId.message_id != message['working_admin_message_id'])
                )
            )
            resident_telegram_id_and_message_id = resident_telegram_id_and_message_id_query.fetchone()

            parsed_resident_telegram_id_and_message_id = {
                'telegram_id': resident_telegram_id_and_message_id[0],
                'message_id': resident_telegram_id_and_message_id[1]
            }

            print(parsed_resident_telegram_id_and_message_id)

            telegram_ids_and_message_ids_by_application_form_id_query = await db.execute(
                select(TelegramIdAndMessageId.telegram_id, TelegramIdAndMessageId.message_id)
                .filter(TelegramIdAndMessageId.application_form_id == application_form_id)
            )
            telegram_ids_and_message_by_application_form_id_ids = telegram_ids_and_message_ids_by_application_form_id_query.all()

            print(telegram_ids_and_message_by_application_form_id_ids)

            for telegram_id_and_message_id_by_application_form_id in telegram_ids_and_message_by_application_form_id_ids:
                if telegram_id_and_message_id_by_application_form_id[0] == message['working_admin_telegram_id'] \
                        and telegram_id_and_message_id_by_application_form_id[1] == message['working_admin_message_id']:
                    await bot.edit_message_caption(
                        caption=render(
                            'application_form/application_form_for_admin.jinja2',
                            body=parsed_application_form_for_admin
                        ),
                        chat_id=telegram_id_and_message_id_by_application_form_id[0],
                        message_id=telegram_id_and_message_id_by_application_form_id[1]
                    )

                    complete_btn = InlineKeyboardButton(text='Выполнить', callback_data='complete_application_form')
                    new_markup = InlineKeyboardMarkup(
                        inline_keyboard=[[complete_btn]]
                    )

                    await bot.edit_message_reply_markup(
                        reply_markup=new_markup,
                        chat_id=telegram_id_and_message_id_by_application_form_id[0],
                        message_id=telegram_id_and_message_id_by_application_form_id[1]
                    )
                elif telegram_id_and_message_id_by_application_form_id[0] == parsed_resident_telegram_id_and_message_id['telegram_id'] \
                        and telegram_id_and_message_id_by_application_form_id[1] == parsed_resident_telegram_id_and_message_id['message_id']:
                    await bot.edit_message_caption(
                        caption=render(
                            'application_form/application_form_for_resident.jinja2',
                            body=parsed_application_form_for_resident
                        ),
                        chat_id=parsed_resident_telegram_id_and_message_id['telegram_id'],
                        message_id=parsed_resident_telegram_id_and_message_id['message_id']
                    )
                else:
                    await bot.delete_message(
                        chat_id=telegram_id_and_message_id_by_application_form_id[0],
                        message_id=telegram_id_and_message_id_by_application_form_id[1]
                    )

    elif message['action'] == 'complete_application_form':
        async with async_session() as db:
            new_status_result = await db.execute(
                select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == message['new_status']))
            new_status_id = new_status_result.scalar()

            application_form_id_result = await db.execute(
                select(TelegramIdAndMessageId.application_form_id).filter(and_(
                    TelegramIdAndMessageId.telegram_id == message['working_admin_telegram_id'],
                    TelegramIdAndMessageId.message_id == message['working_admin_message_id']
                ))
            )
            application_form_id = application_form_id_result.scalar()

            await db.execute(
                update(ApplicationForm).
                where(ApplicationForm.id == application_form_id).
                values(status_id=new_status_id)
            )
            await db.commit()

            application_form_for_resident_query = await db.execute(
                select(
                    ApplicationForm.title,
                    ApplicationForm.description,
                    ApplicationFormStatus.title
                )
                .select_from(User)
                .join(ResidentAdditionalData, ResidentAdditionalData.user_id == User.id)
                .join(ApplicationForm, ApplicationForm.user_id == User.id)
                .join(ApplicationFormStatus, ApplicationFormStatus.id == ApplicationForm.status_id)
                .where(ApplicationForm.id == application_form_id)
            )
            application_form_for_resident = application_form_for_resident_query.fetchone()

            parsed_application_form_for_resident = ApplicationFormForResidentMessage(
                title=application_form_for_resident[0],
                description=application_form_for_resident[1],
                status=application_form_for_resident[2]
            )

            resident_telegram_id_and_message_id_query = await db.execute(
                select(
                    TelegramIdAndMessageId.telegram_id,
                    TelegramIdAndMessageId.message_id
                )
                .join(User, User.telegram_id == TelegramIdAndMessageId.telegram_id)
                .join(ApplicationForm, ApplicationForm.id == TelegramIdAndMessageId.application_form_id)
                .where(
                    (ApplicationForm.id == application_form_id)
                    & (User.id == ApplicationForm.user_id)
                    & (TelegramIdAndMessageId.message_id != message['working_admin_message_id'])
                )
            )
            resident_telegram_id_and_message_id = resident_telegram_id_and_message_id_query.fetchone()

            parsed_resident_telegram_id_and_message_id = {
                'telegram_id': resident_telegram_id_and_message_id[0],
                'message_id': resident_telegram_id_and_message_id[1]
            }

            await bot.delete_message(
                chat_id=message['working_admin_telegram_id'],
                message_id=message['working_admin_message_id']
            )

            await bot.edit_message_caption(
                caption=render(
                    'application_form/application_form_for_resident.jinja2',
                    body=parsed_application_form_for_resident
                ),
                chat_id=parsed_resident_telegram_id_and_message_id['telegram_id'],
                message_id=parsed_resident_telegram_id_and_message_id['message_id']
            )

    elif message['action'] == 'cancel_application_form':
        async with async_session() as db:
            new_status_result = await db.execute(
                select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == message['new_status']))
            new_status_id = new_status_result.scalar()

            application_form_id_result = await db.execute(
                select(TelegramIdAndMessageId.application_form_id).filter(and_(
                    TelegramIdAndMessageId.telegram_id == message['working_admin_telegram_id'],
                    TelegramIdAndMessageId.message_id == message['working_admin_message_id']
                ))
            )
            application_form_id = application_form_id_result.scalar()

            await db.execute(
                update(ApplicationForm).
                where(ApplicationForm.id == application_form_id).
                values(status_id=new_status_id)
            )
            await db.commit()

            application_form_for_resident_query = await db.execute(
                select(
                    ApplicationForm.title,
                    ApplicationForm.description,
                    ApplicationFormStatus.title
                )
                .select_from(User)
                .join(ResidentAdditionalData, ResidentAdditionalData.user_id == User.id)
                .join(ApplicationForm, ApplicationForm.user_id == User.id)
                .join(ApplicationFormStatus, ApplicationFormStatus.id == ApplicationForm.status_id)
                .where(ApplicationForm.id == application_form_id)
            )
            application_form_for_resident = application_form_for_resident_query.fetchone()

            parsed_application_form_for_resident = ApplicationFormForResidentMessage(
                title=application_form_for_resident[0],
                description=application_form_for_resident[1],
                status=application_form_for_resident[2]
            )

            resident_telegram_id_and_message_id_query = await db.execute(
                select(
                    TelegramIdAndMessageId.telegram_id,
                    TelegramIdAndMessageId.message_id
                )
                .join(User, User.telegram_id == TelegramIdAndMessageId.telegram_id)
                .join(ApplicationForm, ApplicationForm.id == TelegramIdAndMessageId.application_form_id)
                .where(
                    (ApplicationForm.id == application_form_id)
                    & (User.id == ApplicationForm.user_id)
                    & (TelegramIdAndMessageId.message_id != message['working_admin_message_id'])
                )
            )
            resident_telegram_id_and_message_id = resident_telegram_id_and_message_id_query.fetchone()

            parsed_resident_telegram_id_and_message_id = {
                'telegram_id': resident_telegram_id_and_message_id[0],
                'message_id': resident_telegram_id_and_message_id[1]
            }

            await bot.delete_message(
                chat_id=message['working_admin_telegram_id'],
                message_id=message['working_admin_message_id']
            )

            await bot.edit_message_caption(
                caption=render(
                    'application_form/application_form_for_resident.jinja2',
                    body=parsed_application_form_for_resident
                ),
                chat_id=parsed_resident_telegram_id_and_message_id['telegram_id'],
                message_id=parsed_resident_telegram_id_and_message_id['message_id']
            )
