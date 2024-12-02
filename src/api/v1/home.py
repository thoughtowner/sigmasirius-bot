import asyncio

import aio_pika
import msgpack
from aio_pika import ExchangeType
from fastapi import Depends
from fastapi.responses import JSONResponse, ORJSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .router import router
from src.storage.db import get_db
from src.storage.rabbit import channel_pool


@router.get("/home")
async def home(
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    test = (
        await session.scalars(
            select(text('1'))
        )
    ).one()
    await asyncio.sleep(5)

    await publish({'test': 'test'})

    return ORJSONResponse({"message": "Hello"})


queue_name = 'test_queue'
queue_name1 = 'test_queue1'


async def publish(body: dict[str, any]) -> None:
    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        exchange = await channel.declare_exchange("first_exchange", ExchangeType.FANOUT, durable=True) # !


        queue = await channel.declare_queue(queue_name, durable=True)
        queue1 = await channel.declare_queue(queue_name1, durable=True)

        # Binding queue
        await queue.bind(exchange, '')
        await queue1.bind(exchange, '')

        await exchange.publish(
            aio_pika.Message(msgpack.packb(body)),
            ''
        )
