import asyncio
import logging
from typing import AsyncGenerator
import json
import urllib.request

import uvicorn

from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

from config.settings import settings
from src.api.tg.router import router as tg_router
from src.api.tech.router import router as tech_router
from src.pages.router import router as pages_router
from src.bg_tasks import background_tasks
from src.bot import dp, bot

from src.logger import LOGGING_CONFIG, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logging.config.dictConfig(LOGGING_CONFIG)

    polling_task: asyncio.Task[None] | None = None

    wh_info = await bot.get_webhook_info()
    if settings.BOT_WEBHOOK_URL:
        # если хотим работать через webhook — установить его (или обновить), но НЕ запускать polling
        if getattr(wh_info, "url", None) != settings.BOT_WEBHOOK_URL:
            await bot.set_webhook(settings.BOT_WEBHOOK_URL)
    else:
        # хотим polling — убедиться, что webhook удалён, и только потом запускать polling
        if getattr(wh_info, "url", None):
            await bot.delete_webhook()
        polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    # try:
    #     wh_info = await bot.get_webhook_info()
    # except Exception:
    #     wh_info = None

    # # Determine webhook target: prefer ngrok public url when available
    # target_url = settings.BOT_WEBHOOK_URL or None
    # try:
    #     with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=0.5) as resp:
    #         data = json.load(resp)
    #         tunnels = data.get('tunnels', [])
    #         if tunnels:
    #             public = tunnels[0].get('public_url')
    #             if public:
    #                 target_url = public.rstrip('/') + '/tg/webhook'
    # except Exception:
    #     pass

    # if target_url:
    #     current = getattr(wh_info, 'url', None)
    #     if current != target_url:
    #         await bot.set_webhook(target_url)
    # else:
    #     polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

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
    app.include_router(pages_router, prefix='', tags=['pages'])

    from fastapi.staticfiles import StaticFiles

    app.mount('/static', StaticFiles(directory='src/static'), name='static')

    app.add_middleware(RawContextMiddleware, plugins=[plugins.CorrelationIdPlugin()])
    return app


async def start_polling():
    logging.config.dictConfig(LOGGING_CONFIG)

    logger.info('Starting polling')

    await bot.delete_webhook()

    logging.error('Dependencies launched')
    await dp.start_polling(bot)


# async def start_bot():
#     try:
#         await bot.send_message(settings.OWNER_TELEGRAM_ID, 'Я запущен!')
#     except:
#         pass

# async def stop_bot():
#     try:
#         await bot.send_message(settings.OWNER_TELEGRAM_ID, 'Бот остановлен!')
#     except:
#         pass


if __name__ == '__main__':
    uvicorn.run('src.app:create_app', factory=True, host='0.0.0.0', port=8000, workers=1)
