from ...mappers import from_application_form_data_to_user, from_application_form_data_to_application_form
from config.settings import settings
from ..storage.db import async_session

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

from aiogram.types import Message, InputFile, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_application_form_status_event(message): # TODO async def handle_application_form_event(message: ApplicationFormStatusMessage)
    if message['action'] == 'take_for_processing':
        pass