from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, TelegramObject

from ..storage.db import async_session

from sqlalchemy import select, and_
from src.model.models import User, Role, UserRole


class AdminMiddleware(BaseMiddleware):

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        current_data = await data['state'].get_data()
        current_telegram_id = current_data['telegram_id']

        async with async_session() as db:
            admin_role_result = await db.execute(select(Role.id).filter(Role.title == 'admin'))
            admin_role_id = admin_role_result.scalar()

            user_result = await db.execute(select(User.id).filter(User.telegram_id == current_telegram_id))
            user_id = user_result.scalar()

            user_role_result = await db.execute(
                select(UserRole).filter(and_(UserRole.user_id == user_id, UserRole.role_id == admin_role_id)))
            user_role = user_role_result.scalar()

            if not user_role:
                raise SkipHandler('Unauthorized')

        return await handler(event, data)
