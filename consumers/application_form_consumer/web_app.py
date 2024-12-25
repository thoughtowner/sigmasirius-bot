import asyncio
import logging
import asyncio
import time
from typing import AsyncGenerator

from contextlib import asynccontextmanager
from fastapi import FastAPI

from consumers.application_form_consumer.api.tech.router import router as tech_router
from .app import application_form_consumer
from .logger import logger, LOGGING_CONFIG


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logging.config.dictConfig(LOGGING_CONFIG)

    logger.info('Starting lifespan')
    task = asyncio.create_task(application_form_consumer())

    logger.info('Started succesfully')
    yield
    task.cancel()
    logger.info('Ending lifespan')

def create_app() -> FastAPI:
    app = FastAPI(docs_url='/swagger', lifespan=lifespan)
    app.include_router(tech_router, prefix='', tags=['tech'])
    return app
