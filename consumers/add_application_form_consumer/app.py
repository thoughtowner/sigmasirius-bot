import logging.config

import aio_pika
import msgpack

from logger import LOGGING_CONFIG, logger, correlation_id_ctx
from storage.rabbit import channel_pool

from ..mappers import from_application_form_data_to_user, from_application_form_data_to_application_form
from config.settings import settings
from storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from consumers.model.models import User, Role, ApplicationForm, ResidentAdditionalData, ApplicationFormStatus, UserRole
from sqlalchemy import insert, select

from consumers.add_application_form_consumer.schema.application_form_for_admins_data import ApplicationFormForAdminsData

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

import io
from src.files_storage.storage_client import images_storage

from aiogram.types.input_file import BufferedInputFile

import base64

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)


async def main() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting add_application_form consumer...')

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel

        await channel.set_qos(prefetch_count=10)

        add_application_form_queue = await channel.declare_queue('add_application_form_queue', durable=True)

        logger.info('Add_application_form consumer started!')
        async with add_application_form_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)
                    application_form_data = msgpack.unpackb(message.body)
                    logger.info("Received message %s", application_form_data)
                    user_instance = from_application_form_data_to_user(application_form_data)
                    application_form_instance = await from_application_form_data_to_application_form(application_form_data)

                    try:
                        async with async_session() as db:
                            images_storage.upload_file(str(application_form_instance.id), io.BytesIO(base64.b64decode(application_form_data['photo'])))

                            user_result = await db.execute(select(User.id).filter(User.telegram_user_id == user_instance.telegram_user_id))
                            user_id = user_result.scalar()

                            application_form_query = insert(ApplicationForm).values(
                                title=application_form_instance.title,
                                description=application_form_instance.description,
                                status_id=application_form_instance.status_id,
                                user_id=user_id
                            ).returning(ApplicationForm.id)

                            application_form_result = await db.execute(application_form_query)
                            application_form_id = application_form_result.scalar()
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

                            admin_role_id_result = await db.execute(
                                select(Role.id).filter(Role.title == 'admin')
                            )
                            admin_role_id = admin_role_id_result.scalar()

                            admins_telegram_user_id_query = await db.execute(
                                select(User.telegram_user_id)
                                .join(UserRole, UserRole.user_id == User.id)
                                .filter(UserRole.role_id == admin_role_id)
                            )
                            admins_telegram_user_id = admins_telegram_user_id_query.scalars().all()

                            application_form_for_admins_data = []
                            for admin_telegram_user_id in admins_telegram_user_id:

                                photo_input_file = BufferedInputFile(base64.b64decode(application_form_data['photo']), str(application_form_instance.id))

                                take_for_processing_btn = InlineKeyboardButton(text='Взять в обработку', callback_data='take_for_processing')
                                cancel_btn = InlineKeyboardButton(text='Отменить', callback_data='cancel')
                                markup = InlineKeyboardMarkup(
                                    inline_keyboard=[[take_for_processing_btn], [cancel_btn]]
                                )

                                application_form_for_admins_message = await bot.send_photo(
                                    photo=photo_input_file,
                                    caption=render(
                                        'application_form_for_admins/application_form_for_admins.jinja2',
                                        application_form_for_admins=parsed_application_form_for_admins
                                    ),
                                    reply_markup=markup,
                                    chat_id=admin_telegram_user_id
                                )

                                # if parsed_application_form_for_admins['telegram_user_id'] == admin_telegram_user_id:
                                #     application_form_for_owner_data = {
                                #         'chat_id': admin_telegram_user_id,
                                #         'message_id': application_form_for_admins_message.message_id
                                #     }
                                # else:
                                #     application_form_for_admins_data.append(
                                #         {
                                #             'chat_id': admin_telegram_user_id,
                                #             'message_id': application_form_for_admins_message.message_id
                                #         }
                                #     )

                                application_form_for_admins_data.append(
                                    {
                                        'chat_id': admin_telegram_user_id,
                                        'message_id': application_form_for_admins_message.message_id
                                    }
                                )

                            # if parsed_application_form_for_admins['telegram_user_id'] not in admins_telegram_user_id:
                            #     photo_input_file = BufferedInputFile(base64.b64decode(application_form_data['photo']), str(application_form_instance.id))
                            #
                            #     application_form_for_owner_message = await bot.send_photo(
                            #         photo=photo_input_file,
                            #         caption=render(
                            #             'application_form_for_admins/application_form_for_admins.jinja2',
                            #             application_form_for_admins=parsed_application_form_for_admins
                            #         ),
                            #         chat_id=parsed_application_form_for_admins['telegram_user_id']
                            #     )
                            #
                            #     application_form_for_owner_data = {
                            #         'chat_id': parsed_application_form_for_admins['telegram_user_id'],
                            #         'message_id': application_form_for_owner_message.message_id
                            #     }

                            photo_input_file = BufferedInputFile(base64.b64decode(application_form_data['photo']), str(application_form_instance.id))

                            application_form_for_owner_message = await bot.send_photo(
                                photo=photo_input_file,
                                caption=render(
                                    'application_form_for_admins/application_form_for_admins.jinja2',
                                    application_form_for_admins=parsed_application_form_for_admins
                                ),
                                chat_id=parsed_application_form_for_admins['telegram_user_id']
                            )

                            application_form_for_owner_data = {
                                'chat_id': parsed_application_form_for_admins['telegram_user_id'],
                                'message_id': application_form_for_owner_message.message_id
                            }

                            async with channel_pool.acquire() as _channel:
                                application_form_for_admins_exchange = await _channel.declare_exchange('application_form_for_admins_exchange')
                                application_form_for_admins_queue = await _channel.declare_queue('application_form_for_admins_queue', durable=True)
                                await application_form_for_admins_queue.bind(application_form_for_admins_exchange, 'application_form_for_admins_queue')
                                await application_form_for_admins_exchange.publish(aio_pika.Message(msgpack.packb(
                                    {
                                        'application_form_for_user_data': {
                                            'admins': application_form_for_admins_data,
                                            'owner': application_form_for_owner_data
                                        },
                                        'caption': parsed_application_form_for_admins
                                    }
                                )), 'application_form_for_admins_queue')

                    except IntegrityError:
                        await bot.send_message(
                            text='При отправке заявки что-то пошло не так!',
                            chat_id=admin_telegram_user_id
                        )
