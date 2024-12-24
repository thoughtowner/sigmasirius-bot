import asyncio
import logging
import uvicorn

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

from config.settings import settings
from src.bg_tasks import background_tasks
from src.bot import setup_bot, setup_dp

from src.api.tg.router import router as tg_router
from src.api.tech.router import router as tech_router

from src.handlers.start.router import router as start_router
from src.handlers.registration.router import router as registration_router
from src.handlers.add_application_form.router import router as add_application_form_router
from src.handlers.callbacks.router import router as callback_router
from src.logger import LOGGING_CONFIG, logger
from src.storage.redis import setup_redis


async def lifespan(app: FastAPI) -> None:
    logging.config.dictConfig(LOGGING_CONFIG)

    logger.info('Starting lifespan')

    dp = Dispatcher()
    setup_dp(dp)
    bot = Bot(token=settings.BOT_TOKEN)
    setup_bot(bot)

    polling_task: asyncio.Task[None] | None = None
    wh_info = await bot.get_webhook_info()
    if settings.BOT_WEBHOOK_URL and wh_info.url != settings.BOT_WEBHOOK_URL:
        await bot.set_webhook(settings.BOT_WEBHOOK_URL)
    else:
        polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    logger.info("Finished start")
    yield

    if polling_task is not None:
        logger.info("Stopping polling...")
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            logger.info("Polling stopped")

    while background_tasks:
        await asyncio.sleep(0)

    logger.info('Ending lifespan')


def create_app() -> FastAPI:
    app = FastAPI(docs_url='/swagger', lifespan=lifespan)
    app.include_router(tg_router, prefix='/tg', tags=['tg'])
    app.include_router(tech_router, prefix='', tags=['tech'])

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

    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(add_application_form_router)
    dp.include_router(callback_router)
    await bot.delete_webhook()

    logging.error('Dependencies launched')
    await dp.start_polling(bot)


if __name__ == '__main__':
    uvicorn.run('src.app:create_app', factory=True, host='0.0.0.0', port=8000, workers=1)
