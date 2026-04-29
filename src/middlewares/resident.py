from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, CallbackQuery, TelegramObject

from ..storage.db import async_session

from sqlalchemy import select
from src.model.models import User, Reservation, ReservationStatus
from src.commands import ADD_APPLICATION_FORM
from datetime import date


class ResidentMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # determine telegram id: prefer stored state, fallback to event.from_user
        current_telegram_id = None
        try:
            current_data = await data['state'].get_data()
            current_telegram_id = current_data.get('telegram_id')
        except Exception:
            current_data = {}

        if not current_telegram_id:
            # try event
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

            # deny admins and repairmen from resident routes
            if user.is_admin or user.is_repairman:
                try:
                    from src.bot import bot
                    await bot.send_message(current_telegram_id, 'У вас нет прав для выполнения этой команды.')
                except Exception:
                    pass
                raise SkipHandler('Unauthorized')

            # If user tries to create an application form, ensure they have an active reservation
            try:
                is_create_application = False
                if isinstance(event, Message):
                    text = (event.text or '').strip()
                    if text == ADD_APPLICATION_FORM:
                        is_create_application = True
                else:
                    # support callback queries from start inline buttons
                    try:
                        cb_data = getattr(event, 'data', None)
                        if cb_data and cb_data.startswith('start_cmd:add_application_form'):
                            is_create_application = True
                    except Exception:
                        is_create_application = False
            except Exception:
                is_create_application = False

            if is_create_application:
                reservation_result = await db.execute(
                    select(Reservation).filter(
                        Reservation.user_id == user.id,
                        Reservation.status == ReservationStatus.IN_PROGRESS
                    )
                )
                reservation = reservation_result.scalars().first()
                if not reservation:
                    try:
                        from src.bot import bot
                        await bot.send_message(current_telegram_id, 'У вас нет активной брони. Перед созданием заявки выполните бронь.')
                    except Exception:
                        pass
                    raise SkipHandler('Unauthorized')

        return await handler(event, data)
