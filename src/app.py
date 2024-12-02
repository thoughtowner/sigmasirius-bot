import asyncio
import logging
import uvicorn

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

from config.settings import settings
from src.api.v1.router import router as v1_router
from src.api.tg.router import router as tg_router
from src.bg_tasks import background_tasks
from src.bot import setup_bot, setup_dp
from src.handlers.callback.router import router as callback_router
from src.handlers.command.router import router as command_router
from src.handlers.message.router import router as message_router
from src.logger import LOGGING_CONFIG, logger
from src.storage.redis import setup_redis


async def lifespan(app: FastAPI) -> None:
    logging.config.dictConfig(LOGGING_CONFIG)

    logger.info('Starting lifespan')

    dp = Dispatcher()
    setup_dp(dp)
    bot = Bot(token=settings.BOT_TOKEN)
    setup_bot(bot)

    temp = await bot.get_webhook_info()
    await bot.set_webhook(settings.BOT_WEBHOOK_URL)
    yield

    while background_tasks:
        await asyncio.sleep(0)

    logger.info('Ending lifespan')


def create_app() -> FastAPI:
    app = FastAPI(docs_url='/swagger', lifespan=lifespan)
    app.include_router(v1_router, prefix='/v1', tags=['v1'])
    app.include_router(tg_router, prefix='/tg', tags=['tg'])

    app.add_middleware(RawContextMiddleware, plugins=[plugins.CorrelationIdPlugin()])
    return app


async def start_polling():
    logging.error('Starting polling')
    redis = setup_redis()
    storage = RedisStorage(redis=redis)

    dp = Dispatcher(storage=storage)

    setup_dp(dp)
    bot = Bot(token=settings.BOT_TOKEN)
    setup_bot(bot)

    dp.include_router(command_router)
    dp.include_router(message_router)
    dp.include_router(callback_router)
    await bot.delete_webhook()

    logging.error('Dependencies launched')
    await dp.start_polling(bot)


if __name__ == '__main__':
    if settings.BOT_WEBHOOK_URL:
        uvicorn.run('src.app:create_app', factory=True, host='0.0.0.0', port=8000, workers=1)
    else:
        asyncio.run(start_polling())
