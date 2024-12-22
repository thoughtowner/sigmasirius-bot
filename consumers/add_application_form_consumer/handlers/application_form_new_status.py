from ...mappers import from_application_form_data_to_user, from_application_form_data_to_application_form
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from consumers.model.models import User, Role, ApplicationForm, ResidentAdditionalData, ApplicationFormStatus, UserRole
from sqlalchemy import insert, select, update

from consumers.add_application_form_consumer.schema.application_form_for_admins_data import ApplicationFormForAdminsData

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_application_form_new_status_event(message): # TODO async def handle_application_form_event(message: ApplicationFormStatusMessage)
    if message['action'] == 'take_for_processing':
        clicked_admin_telegram_user_id = message['clicked_admin_telegram_user_id']
        clicked_admin_message_id = message['clicked_admin_message_id']
        owner_telegram_user_id = message['owner_telegram_user_id']
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
                        User.telegram_user_id,
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

                parsed_application_form_for_admins = ApplicationFormForAdminsData(
                    telegram_user_id=application_form_for_admins[0],
                    resident_full_name=application_form_for_admins[1],
                    resident_phone_number=application_form_for_admins[2],
                    resident_room=application_form_for_admins[3],
                    application_form_id=str(application_form_for_admins[4]),
                    title=application_form_for_admins[5],
                    description=application_form_for_admins[6],
                    status=application_form_for_admins[7]
                )

                # admin_role_id_result = await db.execute(
                #     select(Role.id).filter(Role.title == 'admin')
                # )
                # admin_role_id = admin_role_id_result.scalar()
                #
                # admins_telegram_user_id_query = await db.execute(
                #     select(User.telegram_user_id)
                #     .join(UserRole, UserRole.user_id == User.id)
                #     .filter(UserRole.role_id == admin_role_id)
                # )
                # admins_telegram_user_id = admins_telegram_user_id_query.scalars().all()
                #
                # for admin_telegram_user_id in admins_telegram_user_id:

                for application_form_for_admin_data in application_form_for_admins_response_message['application_form_for_user_data']['admins']:
                    if application_form_for_admin_data['chat_id'] == clicked_admin_telegram_user_id and application_form_for_admin_data['message_id'] == clicked_admin_message_id:
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

                        # application_forms_data = await state.get_data()
                        # application_forms_data[caption['application_form_id']] = {
                        #     'admin_data': {
                        #         'chat_id': application_form_for_admin_data['chat_id'],
                        #         'message_id': application_form_for_admin_data['message_id']
                        #     },
                        #     'owner_data': {
                        #         'chat_id': application_form_for_owner_data['chat_id'],
                        #         'message_id': application_form_for_owner_data['message_id']
                        #     },
                        #     'caption': caption
                        # }
                        # await state.update_data(application_forms_data=application_forms_data)
                    else:
                        await bot.delete_message(chat_id=application_form_for_admin_data['chat_id'], message_id=application_form_for_admin_data['message_id'])

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=parsed_application_form_for_admins
                    ),
                    chat_id=owner_telegram_user_id,
                    message_id=owner_message_id
                )

                # async with channel_pool.acquire() as _channel:
                #     application_form_for_admins_exchange = await _channel.declare_exchange('application_form_for_admins_exchange')
                #     application_form_for_admins_queue = await _channel.declare_queue('application_form_for_admins_queue', durable=True)
                #     await application_form_for_admins_queue.bind(application_form_for_admins_exchange, 'application_form_for_admins_queue')
                #     await application_form_for_admins_exchange.publish(aio_pika.Message(msgpack.packb(
                #         {
                #             'application_form_for_user_data': {
                #                 'admins': application_form_for_admins_data,
                #                 'owner': application_form_for_owner_data
                #             },
                #             'application_form_id': parsed_application_form_for_admins['application_form_id']
                #         }
                #     )), 'application_form_for_admins_queue')


                # for application_form_for_admin_data in application_form_for_admins_data:
                #     if admin_telegram_user_id == clicked_admin_telegram_user_id:
                #         await bot.edit_message_caption(
                #             caption=render(
                #                 'application_form_for_admins/application_form_for_admins.jinja2',
                #                 application_form_for_admins=parsed_application_form_for_admins
                #             ),
                #             message_id=clicked_admin_message_id,
                #             chat_id = clicked_admin_telegram_user_id
                #         )
                #
                #         complete_btn = InlineKeyboardButton(text='Выполнить', callback_data='complete')
                #         new_markup = InlineKeyboardMarkup(
                #             inline_keyboard=[[complete_btn]]
                #         )
                #
                #         await bot.edit_message_reply_markup(
                #             message_id=clicked_admin_message_id,
                #             chat_id=clicked_admin_telegram_user_id,
                #             reply_markup=new_markup
                #         )
                #     else:
                #         await bot.delete_message(chat_id=admin_telegram_user_id, message_id=application_form_for_admin_data['message_id'])
                #
                #         # application_forms_data = await state.get_data()
                #         # application_forms_data[caption['application_form_id']] = {
                #         #     'admin_data': {
                #         #         'chat_id': application_form_for_admin_data['chat_id'],
                #         #         'message_id': application_form_for_admin_data['message_id']
                #         #     },
                #         #     'owner_data': {
                #         #         'chat_id': application_form_for_owner_data['chat_id'],
                #         #         'message_id': application_form_for_owner_data['message_id']
                #         #     },
                #         #     'caption': caption
                #         # }
                #         # await state.update_data(application_forms_data=application_forms_data)

        except IntegrityError as e:
            print(e)
            await bot.send_message(
                text='При отправке заявки что-то пошло не так!',
                chat_id=clicked_admin_telegram_user_id
            )

    elif message['action'] == 'complete':
        clicked_admin_telegram_user_id = message['clicked_admin_telegram_user_id']
        clicked_admin_message_id = message['clicked_admin_message_id']
        owner_telegram_user_id = message['owner_telegram_user_id']
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
                        User.telegram_user_id,
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

                parsed_application_form_for_admins = ApplicationFormForAdminsData(
                    telegram_user_id=application_form_for_admins[0],
                    resident_full_name=application_form_for_admins[1],
                    resident_phone_number=application_form_for_admins[2],
                    resident_room=application_form_for_admins[3],
                    application_form_id=str(application_form_for_admins[4]),
                    title=application_form_for_admins[5],
                    description=application_form_for_admins[6],
                    status=application_form_for_admins[7]
                )

                for application_form_for_admin_data in application_form_for_admins_response_message['application_form_for_user_data']['admins']:
                    if application_form_for_admin_data['chat_id'] == clicked_admin_telegram_user_id and application_form_for_admin_data['message_id'] == clicked_admin_message_id:
                        await bot.delete_message(chat_id=application_form_for_admin_data['chat_id'], message_id=application_form_for_admin_data['message_id'])

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=parsed_application_form_for_admins
                    ),
                    chat_id=owner_telegram_user_id,
                    message_id=owner_message_id
                )

        except IntegrityError as e:
            print(e)
            await bot.send_message(
                text='При отправке заявки что-то пошло не так!',
                chat_id=clicked_admin_telegram_user_id
            )

    elif message['action'] == 'cancel':
        clicked_admin_telegram_user_id = message['clicked_admin_telegram_user_id']
        clicked_admin_message_id = message['clicked_admin_message_id']
        owner_telegram_user_id = message['owner_telegram_user_id']
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
                        User.telegram_user_id,
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

                parsed_application_form_for_admins = ApplicationFormForAdminsData(
                    telegram_user_id=application_form_for_admins[0],
                    resident_full_name=application_form_for_admins[1],
                    resident_phone_number=application_form_for_admins[2],
                    resident_room=application_form_for_admins[3],
                    application_form_id=str(application_form_for_admins[4]),
                    title=application_form_for_admins[5],
                    description=application_form_for_admins[6],
                    status=application_form_for_admins[7]
                )

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=parsed_application_form_for_admins
                    ),
                    chat_id=clicked_admin_telegram_user_id,
                    message_id=clicked_admin_message_id
                )

                await bot.edit_message_caption(
                    caption=render(
                        'application_form_for_admins/application_form_for_admins.jinja2',
                        application_form_for_admins=parsed_application_form_for_admins
                    ),
                    chat_id=owner_telegram_user_id,
                    message_id=owner_message_id
                )

        except IntegrityError as e:
            print(e)
            await bot.send_message(
                text='При отправке заявки что-то пошло не так!',
                chat_id=clicked_admin_telegram_user_id
            )
