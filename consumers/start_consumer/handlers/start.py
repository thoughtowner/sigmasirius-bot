from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, ApplicationForm
from sqlalchemy import select, insert

from ..schema.start import StartMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.templates.env import render

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_start_event(message): # TODO async def handle_start_event(message: StartMessage)
    async with async_session() as db:
        if message['flag']:
            user_query = insert(User).values(
                telegram_id=message['telegram_id'],
                full_name=message['full_name'],
                phone_number=message['phone_number'],
            )
            await db.execute(user_query)
            await db.commit()

        user_query = await db.execute(
            select(User).filter(User.telegram_id == message['telegram_id']))
        user = user_query.scalar()

        application_form_query = await db.execute(
            select(ApplicationForm).filter(ApplicationForm.user_id == user.id))
        application_form = application_form_query.scalar()

        if user.is_admin:
            await bot.send_message(
                text=render('start/start_for_admin.jinja2'),
                chat_id=message['telegram_id']
            )
        elif user.is_repairman:
            await bot.send_message(
                text=render('start/start_for_repairman.jinja2'),
                chat_id=message['telegram_id']
            )
        else:
            if application_form:
                await bot.send_message(
                    text=render('start/start_for_resident_with_reservation.jinja2'),
                    chat_id=message['telegram_id']
                )
            else:
                await bot.send_message(
                    text=render('start/start_for_resident_without_reservation.jinja2'),
                    chat_id=message['telegram_id']
                )
