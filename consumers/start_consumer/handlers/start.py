from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from ..model.models import User, Role, ApplicationForm, ResidentAdditionalData, ApplicationFormStatus, UserRole
from sqlalchemy import insert, select

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
    try:
        async with async_session() as db:
            user_query = insert(User).values(
                telegram_id=message['telegram_id']
            )

            await db.execute(user_query)

            await db.commit()

            await bot.send_message(
                text=render('start/start.jinja2'),
                chat_id=message['telegram_id']
            )
    except IntegrityError:
        await bot.send_message(
            text=render('start/start.jinja2'),
            chat_id=message['telegram_id']
        )
