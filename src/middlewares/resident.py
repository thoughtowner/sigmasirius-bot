from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, TelegramObject

from ..storage.db import async_session

from sqlalchemy import select
from src.model.models import User, Resident


class ResidentMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        current_data = await data['state'].get_data()
        current_telegram_id = current_data['telegram_id']

        async with async_session() as db:
            user_result = await db.execute(select(User.id).filter(User.telegram_id == current_telegram_id))
            user_id = user_result.scalar()

            resident_result = await db.execute(select(Resident).filter(Resident.user_id == user_id))
            resident = resident_result.scalar()

            if not resident:
                raise SkipHandler('Unauthorized')

        return await handler(event, data)
