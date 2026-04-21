from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, TelegramObject

from ..storage.db import async_session

from sqlalchemy import select
from src.model.models import User


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
            user_result = await db.execute(select(User).filter(User.telegram_id == current_telegram_id))
            user = user_result.scalar()

            if not user:
                # user not registered -> ask to run /start
                try:
                    from src.bot import bot
                    await bot.send_message(current_telegram_id, 'Перед выполнением команды выполните /start')
                except Exception:
                    pass
                raise SkipHandler('Unauthorized')

            if not user.is_admin:
                try:
                    from src.bot import bot
                    await bot.send_message(current_telegram_id, 'У вас нет прав для выполнения этой команды.')
                except Exception:
                    pass
                raise SkipHandler('Unauthorized')

        return await handler(event, data)
