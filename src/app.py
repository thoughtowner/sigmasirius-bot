import asyncio
import logging
from typing import AsyncGenerator

import uvicorn

from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

from config.settings import settings
from src.api.tg.router import router as tg_router
from src.api.tech.router import router as tech_router
from src.bg_tasks import background_tasks
from src.bot import dp, bot

from src.logger import LOGGING_CONFIG, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logging.config.dictConfig(LOGGING_CONFIG)

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

    await bot.delete_webhook()

    logger.info('Ending lifespan')


def create_app() -> FastAPI:
    app = FastAPI(docs_url='/swagger', lifespan=lifespan)
    app.include_router(tg_router, prefix='/tg', tags=['tg'])
    app.include_router(tech_router, prefix='', tags=['tech'])

    app.add_middleware(RawContextMiddleware, plugins=[plugins.CorrelationIdPlugin()])
    return app


async def start_polling():
    logging.config.dictConfig(LOGGING_CONFIG)

    logger.info('Starting polling')

    await bot.delete_webhook()

    logging.error('Dependencies launched')
    await dp.start_polling(bot)


if __name__ == '__main__':
    uvicorn.run('src.app:create_app', factory=True, host='0.0.0.0', port=8000, workers=1)
