from ..mappers import get_user
from config.settings import settings
from ..storage.db import async_session

from ..model.models import User
from sqlalchemy import update, select

from ..schema import RepairmanMessage

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.msg_templates.env import render
from datetime import datetime

from consumers.start_consumer.handlers.start import handle_start_event

import io
from src.files_storage.storage_client import images_storage

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

import aio_pika
import msgpack

from ..logger import LOGGING_CONFIG, logger, correlation_id_ctx
from ..storage.rabbit import channel_pool
import uuid

from datetime import date

import qrcode


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_quit_as_repairman_event(message): # TODO async def handle_quit_as_repairman_event(message: RepairmanMessage)
    async with async_session() as db:
        user_result = await db.execute(
            select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

        # await db.execute(
        #     update(User).where(User.id == user_id).values(is_repairman=True, got_role_from_date=date.today())
        # )
        # await db.commit()

        if not message['is_test_data']:
            buf = io.BytesIO()
            img = qrcode.make('quit_as_repairman/' + str(user_id))
            img.save(buf, format='PNG')
            buf.seek(0)
            image_file = BufferedInputFile(file=buf.read(), filename='quit_as_repairman_qr.png')
            
            # import bot lazily to avoid circular import at module import time
            from src.bot import bot
            await bot.send_photo(
                chat_id=message['telegram_id'], photo=image_file,
                caption='Ваш QR-код для уволнения с должности ремонтника. Покажите его на ресепшене.',
            )

    await handle_start_event(message=message)
