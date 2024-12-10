from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

import aio_pika
from src.storage.rabbit import channel_pool
import msgpack
from aio_pika import ExchangeType
from starlette_context.header_keys import HeaderKeys
from starlette_context import context

from config.settings import settings
from consumers.registration_consumer.schema.registration_data import RegistrationData
from src.states.registration import Registration
from .router import router
from src.keyboard_buttons.registration import BUILDINGS_ROW_BUTTONS, ENTRANCES_ROW_BUTTONS, FLOORS_ROW_BUTTONS, ROOM_NUMBERS_BY_FLOOR_ROW_BUTTONS
from aiogram.types import ReplyKeyboardRemove
from src.validators.registration.validators import FullNameValidator, PhoneNumberValidator
from src.validators.registration import errors as validation
from src.messages import registration as msg
from src.keyboard_buttons.texts import BUILDINGS, ENTRANCES, ROOM_NUMBERS_BY_FLOOR
from src.commands import REGISTRATION
from src.logger import LOGGING_CONFIG, logger
import logging.config

from aio_pika.exceptions import QueueEmpty
import asyncio


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == REGISTRATION)
async def start_registration(message: Message, state: FSMContext):
    await state.update_data(telegram_user_id=message.from_user.id)