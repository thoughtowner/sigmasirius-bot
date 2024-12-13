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
                            user_result = await db.execute(select(User.id).filter(User.telegram_user_id == user_instance.telegram_user_id))
                            user_id = user_result.scalar()

                            application_form_query = insert(ApplicationForm).values(
                                title=application_form_instance.title,
                                description=application_form_instance.description,
                                photo=application_form_instance.photo,
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
                                    ApplicationForm.title,
                                    ApplicationForm.description,
                                    ApplicationForm.photo,
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
                                title=application_form_for_admins[4],
                                description=application_form_for_admins[5],
                                photo=application_form_for_admins[6],
                                status=application_form_for_admins[7]
                            )

                            admin_role_id_result = await db.execute(
                                select(Role.id).filter(Role.title == 'admin')
                            )
                            admin_role_id = admin_role_id_result.scalar()

                            admin_ids_query = await db.execute(
                                select(UserRole.user_id).filter(UserRole.role_id == admin_role_id)
                            )
                            admin_ids = admin_ids_query.scalars().all()

                            for admin_id in admin_ids:
                                # await bot.send_message(
                                #     text=render('application_form_for_admins/application_form_for_admins.jinja2',
                                #                 application_form_for_admins=parsed_application_form_for_admins),
                                #     chat_id=admin_id
                                # )

                                await bot.send_photo(
                                    photo=msgpack.unpackb(parsed_application_form_for_admins['photo']),
                                    caption=render('application_form_for_admins/application_form_for_admins.jinja2',
                                                   application_form_for_admins=parsed_application_form_for_admins),
                                    chat_id=admin_id
                                )
                    except IntegrityError:
                        await bot.send_message(
                            text='При отправке заявки что-то пошло не так!',
                            chat_id=admin_id
                        )
