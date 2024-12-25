from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from config.settings import settings
from src.handlers.unauthorized.router import router as unauthorized_router
from src.handlers.admin.router import router as admin_router
from src.handlers.resident.router import router as resident_router
from src.storage.redis import redis_storage

dp = Dispatcher(storage=RedisStorage(redis=redis_storage))
default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

dp.include_router(unauthorized_router)
dp.include_router(admin_router)
dp.include_router(resident_router)
