import asyncio
import logging

from aiogram import Dispatcher, Bot
from fastapi import FastAPI

from src.api.v1.router import router as v1_router
from src.bg_tasks import background_tasks
from src.bot import setup_bot, setup_dp


async def lifespan(app: FastAPI) -> None:
    logging.getLogger("uvicorn").info('Starting lifespan')

    dp = Dispatcher()
    setup_dp(dp)
    bot = Bot(token='6883664445:AAGsg8Swwudod-1rXrxvk-HAgew5XW8AZq8')
    setup_bot(bot)

    from . import handlers
    temp = await bot.get_webhook_info()
    await bot.set_webhook('https://3e38-5-139-224-187.ngrok-free.app/v1/home')
    yield

    while background_tasks:
        await asyncio.sleep(0)

    logging.getLogger("uvicorn").info('Ending lifespan')


def create_app() -> FastAPI:
    app = FastAPI(docs_url='/swagger', lifespan=lifespan)
    app.include_router(v1_router, prefix='/v1', tags=['v1'])

    return app
