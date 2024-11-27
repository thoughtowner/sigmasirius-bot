import asyncio

from aiogram.types import Update
from fastapi import Depends
from fastapi.responses import JSONResponse, ORJSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from .router import router
from ...bg_tasks import background_tasks
from ...bot import get_dp, get_bot
from ...storage.db import get_db


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
    return ORJSONResponse({"message": test})


@router.post("/home")
async def home_post(
    request: Request,
    # session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    a = 1
    data = await request.json()
    update = Update(**data)
    dp = get_dp()

    task = asyncio.create_task(dp.feed_webhook_update(get_bot(), update))
    background_tasks.add(task)

    return ORJSONResponse({"message": "Hello"})


@router.patch("/home")
async def home_patch(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    test = (
        await session.scalars(
            select(text('1'))
        )
    ).one()
    await asyncio.sleep(5)
    return ORJSONResponse({"message": "Hello"})


@router.put("/home")
async def home_put(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    test = (
        await session.scalars(
            select(text('1'))
        )
    ).one()
    await asyncio.sleep(5)
    return ORJSONResponse({"message": "Hello"})
