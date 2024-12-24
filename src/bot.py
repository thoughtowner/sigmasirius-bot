from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from config.settings import settings
from src.handlers.start.router import router as start_router
from src.handlers.registration.router import router as registration_router
from src.handlers.add_application_form.router import router as add_application_form_router
from src.handlers.callbacks.router import router as callback_router
from src.storage.redis import redis_storage

dp = Dispatcher(storage=RedisStorage(redis=redis_storage))
default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

dp.include_router(start_router)
dp.include_router(registration_router)
dp.include_router(add_application_form_router)
dp.include_router(callback_router)
