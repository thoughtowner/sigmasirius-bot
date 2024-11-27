import asyncio

from fastapi import Depends
from fastapi.responses import JSONResponse, ORJSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .router import router
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
    return ORJSONResponse({"message": "Hello"})
