from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, TelegramObject

from ..storage.db import async_session

from sqlalchemy import select
from src.model.models import User


class RepairmanMiddleware(BaseMiddleware):

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        try:
            current_data = await data['state'].get_data()
            current_telegram_id = current_data.get('telegram_id')
        except Exception:
            current_data = {}
            current_telegram_id = None

        if not current_telegram_id:
            try:
                current_telegram_id = event.from_user.id  # type: ignore
            except Exception:
                current_telegram_id = None

        if not current_telegram_id:
            raise SkipHandler('Unauthorized')

        async with async_session() as db:
            user_result = await db.execute(select(User).filter(User.telegram_id == current_telegram_id))
            user = user_result.scalar()

            if not user:
                try:
                    from src.bot import bot
                    await bot.send_message(current_telegram_id, 'Перед выполнением команды выполните /start')
                except Exception:
                    pass
                raise SkipHandler('Unauthorized')

            if not user.is_repairman:
                try:
                    from src.bot import bot
                    await bot.send_message(current_telegram_id, 'У вас нет прав для выполнения этой команды.')
                except Exception:
                    pass
                raise SkipHandler('Unauthorized')

        return await handler(event, data)
