from ..mappers import get_user, get_application_form
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, Role, ApplicationForm, ResidentAdditionalData, ApplicationFormStatus, UserRole
from sqlalchemy import insert, select, update

from ..schema.application_form_for_admin import ApplicationFormForAdminMessage

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
        clicked_admin_telegram_id = message['clicked_admin_telegram_id']
        clicked_admin_message_id = message['clicked_admin_message_id']
        owner_telegram_id = message['owner_telegram_id']
        owner_message_id = message['owner_message_id']
        application_form_id = message['application_form_id']
        new_status = message['new_status']
        application_form_for_admins_response_message = message['application_form_for_admins_response_message']

        try:
            async with async_session() as db:
                new_status_result = await db.execute(select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == new_status))
                new_status_id = new_status_result.scalar()

                await db.execute(
                    update(ApplicationForm).
                    where(ApplicationForm.id == application_form_id).
                    values(status_id=new_status_id)
                )
                await db.commit()

                application_form_for_admins_query = (
                    select(
                        User.telegram_id,
                        ResidentAdditionalData.full_name,
                        ResidentAdditionalData.phone_number,
                        ResidentAdditionalData.room,
                        ApplicationForm.id,
                        ApplicationForm.title,
                        ApplicationForm.description,
                        ApplicationFormStatus.title
                    )
                    .join(ResidentAdditionalData, ResidentAdditionalData.user_id == User.id)
                    .join(ApplicationForm, ApplicationForm.user_id == User.id)
                    .join(ApplicationFormStatus, ApplicationFormStatus.id == ApplicationForm.status_id)
                    .where(ApplicationForm.id == application_form_id)
                )

                application_form_for_admins_result = await db.execute(application_form_for_admins_query)
                application_form_for_admins = application_form_for_admins_result.fetchone()

                parsed_application_form_for_admins = ApplicationFormForAdminMessage(
                    telegram_id=application_form_for_admins[0],
                    resident_full_name=application_form_for_admins[1],
                    resident_phone_number=application_form_for_admins[2],
                    resident_room=application_form_for_admins[3],
                    application_form_id=str(application_form_for_admins[4]),
                    title=application_form_for_admins[5],
                    description=application_form_for_admins[6],
                    status=application_form_for_admins[7]
                )

                for application_form_for_admin_data in application_form_for_admins_response_message['application_form_for_user_data']['admins']:
                    if application_form_for_admin_data['chat_id'] == clicked_admin_telegram_id and application_form_for_admin_data['message_id'] == clicked_admin_message_id:
                        await bot.edit_message_caption(
                            caption=render(
                                'application_form_for_admins/application_form_for_admins.jinja2',
                                application_form_for_admins=parsed_application_form_for_admins
                            ),
                            chat_id=application_form_for_admin_data['chat_id'],
                            message_id=application_form_for_admin_data['message_id']
                        )

                        complete_btn = InlineKeyboardButton(text='Выполнить', callback_data='complete')
                        new_markup = InlineKeyboardMarkup(
                            inline_keyboard=[[complete_btn]]
                        )

                        await bot.edit_message_reply_markup(
                            chat_id=application_form_for_admin_data['chat_id'],
                            message_id=application_form_for_admin_data['message_id'],
                            reply_markup=new_markup
                        )

                    else:
                        await bot.delete_message(chat_id=application_form_for_admin_data['chat_id'], message_id=application_form_for_admin_data['message_id'])

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=parsed_application_form_for_admins
                    ),
                    chat_id=owner_telegram_id,
                    message_id=owner_message_id
                )

        except IntegrityError as e:
            print(e)
            await bot.send_message(
                text='При отправке заявки что-то пошло не так!',
                chat_id=clicked_admin_telegram_id
            )

    elif message['action'] == 'complete_application_form':
        clicked_admin_telegram_id = message['clicked_admin_telegram_id']
        clicked_admin_message_id = message['clicked_admin_message_id']
        owner_telegram_id = message['owner_telegram_id']
        owner_message_id = message['owner_message_id']
        application_form_id = message['application_form_id']
        new_status = message['new_status']
        application_form_for_admins_response_message = message['application_form_for_admins_response_message']

        try:
            async with async_session() as db:
                new_status_result = await db.execute(select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == new_status))
                new_status_id = new_status_result.scalar()

                await db.execute(
                    update(ApplicationForm).
                    where(ApplicationForm.id == application_form_id).
                    values(status_id=new_status_id)
                )
                await db.commit()

                application_form_for_admins_query = (
                    select(
                        User.telegram_id,
                        ResidentAdditionalData.full_name,
                        ResidentAdditionalData.phone_number,
                        ResidentAdditionalData.room,
                        ApplicationForm.id,
                        ApplicationForm.title,
                        ApplicationForm.description,
                        ApplicationFormStatus.title
                    )
                    .join(ResidentAdditionalData, ResidentAdditionalData.user_id == User.id)
                    .join(ApplicationForm, ApplicationForm.user_id == User.id)
                    .join(ApplicationFormStatus, ApplicationFormStatus.id == ApplicationForm.status_id)
                    .where(ApplicationForm.id == application_form_id)
                )

                application_form_for_admins_result = await db.execute(application_form_for_admins_query)
                application_form_for_admins = application_form_for_admins_result.fetchone()

                parsed_application_form_for_admins = ApplicationFormForAdminMessage(
                    telegram_id=application_form_for_admins[0],
                    resident_full_name=application_form_for_admins[1],
                    resident_phone_number=application_form_for_admins[2],
                    resident_room=application_form_for_admins[3],
                    application_form_id=str(application_form_for_admins[4]),
                    title=application_form_for_admins[5],
                    description=application_form_for_admins[6],
                    status=application_form_for_admins[7]
                )

                for application_form_for_admin_data in application_form_for_admins_response_message['application_form_for_user_data']['admins']:
                    if application_form_for_admin_data['chat_id'] == clicked_admin_telegram_id and application_form_for_admin_data['message_id'] == clicked_admin_message_id:
                        await bot.delete_message(chat_id=application_form_for_admin_data['chat_id'], message_id=application_form_for_admin_data['message_id'])

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=parsed_application_form_for_admins
                    ),
                    chat_id=owner_telegram_id,
                    message_id=owner_message_id
                )

        except IntegrityError as e:
            print(e)
            await bot.send_message(
                text='При отправке заявки что-то пошло не так!',
                chat_id=clicked_admin_telegram_id
            )

    elif message['action'] == 'cancel_application_form':
        clicked_admin_telegram_id = message['clicked_admin_telegram_id']
        clicked_admin_message_id = message['clicked_admin_message_id']
        owner_telegram_id = message['owner_telegram_id']
        owner_message_id = message['owner_message_id']
        application_form_id = message['application_form_id']
        new_status = message['new_status']
        application_form_for_admins_response_message = message['application_form_for_admins_response_message']

        try:
            async with async_session() as db:
                new_status_result = await db.execute(select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == new_status))
                new_status_id = new_status_result.scalar()

                await db.execute(
                    update(ApplicationForm).
                    where(ApplicationForm.id == application_form_id).
                    values(status_id=new_status_id)
                )
                await db.commit()

                application_form_for_admins_query = (
                    select(
                        User.telegram_id,
                        ResidentAdditionalData.full_name,
                        ResidentAdditionalData.phone_number,
                        ResidentAdditionalData.room,
                        ApplicationForm.id,
                        ApplicationForm.title,
                        ApplicationForm.description,
                        ApplicationFormStatus.title
                    )
                    .join(ResidentAdditionalData, ResidentAdditionalData.user_id == User.id)
                    .join(ApplicationForm, ApplicationForm.user_id == User.id)
                    .join(ApplicationFormStatus, ApplicationFormStatus.id == ApplicationForm.status_id)
                    .where(ApplicationForm.id == application_form_id)
                )

                application_form_for_admins_result = await db.execute(application_form_for_admins_query)
                application_form_for_admins = application_form_for_admins_result.fetchone()

                parsed_application_form_for_admins = ApplicationFormForAdminMessage(
                    telegram_id=application_form_for_admins[0],
                    resident_full_name=application_form_for_admins[1],
                    resident_phone_number=application_form_for_admins[2],
                    resident_room=application_form_for_admins[3],
                    application_form_id=str(application_form_for_admins[4]),
                    title=application_form_for_admins[5],
                    description=application_form_for_admins[6],
                    status=application_form_for_admins[7]
                )

                for application_form_for_admin_data in application_form_for_admins_response_message['application_form_for_user_data']['admins']:
                    if application_form_for_admin_data['chat_id'] == clicked_admin_telegram_id and application_form_for_admin_data['message_id'] == clicked_admin_message_id:
                        await bot.delete_message(chat_id=application_form_for_admin_data['chat_id'], message_id=application_form_for_admin_data['message_id'])

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=parsed_application_form_for_admins
                    ),
                    chat_id=owner_telegram_id,
                    message_id=owner_message_id
                )

        except IntegrityError:
            await bot.send_message(
                text='При отправке заявки что-то пошло не так!',
                chat_id=clicked_admin_telegram_id
            )