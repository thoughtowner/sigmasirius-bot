from ..storage.db import async_session
from ..model.models import User, Reservation, ReservationStatus
from sqlalchemy import select, delete
from config.settings import settings
import aio_pika
import msgpack
from aio_pika import ExchangeType
from ..storage.rabbit import channel_pool
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from ..logger import LOGGING_CONFIG, logger
import io
from src.files_storage.storage_client import images_storage
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

# import handle_start_event lazily where needed to avoid circular imports


default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)


async def handle_list_my_reservations_event(message):
    telegram_id = message.get('telegram_id')
    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            reservations = []
        else:
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status == ReservationStatus.UNCONFIRM))
            reservations = res_q.scalars().all()

    # send reservations directly to the user via bot (QR + text + cancel button)
    from src.bot import bot
    for r in reservations:
        reservation_id = str(r.id)
        object_name = f"reservation/{reservation_id}.png"
        try:
            raw = images_storage.get_file(object_name)
        except Exception:
            raw = None

        if not raw:
            await bot.send_message(chat_id=telegram_id, text='QR-код не найден в хранилище.')
            # still send text data
            text = (
                f"ID: {reservation_id}\n"
                f"Статус: {r.status.value}\n"
                f"Гостей: {r.people_quantity}\n"
                f"Класс: {r.room_class.value}\n"
                f"Заезд: {r.check_in_date}\n"
                f"Выезд: {r.eviction_date}\n"
            )
            await bot.send_message(chat_id=telegram_id, text=text)
            continue

        buf = io.BytesIO(raw)
        buf.seek(0)
        image_file = BufferedInputFile(file=buf.read(), filename=f'{reservation_id}_reservation_qr.png')

        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отменить', callback_data=f'cancel_by_id:{reservation_id}')]])

        caption = (
            f"ID: {reservation_id}\n"
            f"Статус: {r.status.value}\n"
            f"Гостей: {r.people_quantity}\n"
            f"Класс: {r.room_class.value}\n"
            f"Заезд: {r.check_in_date}\n"
            f"Выезд: {r.eviction_date}\n"
        )

        sent = await bot.send_photo(chat_id=telegram_id, photo=image_file, caption=caption, reply_markup=kb)

        # store reverse mapping to allow clearing markups later
        try:
            from src.storage.redis import redis_storage
            import json
            member = {'telegram_id': telegram_id, 'message_id': sent.message_id}
            key = f'reservation:{reservation_id}:members'
            current_raw = await redis_storage.get(key)
            if current_raw:
                try:
                    current = json.loads(current_raw)
                except Exception:
                    current = []
            else:
                current = []
            current.append(member)
            await redis_storage.set(key, json.dumps(current))
            await redis_storage.set(f'reservation_message_map:{telegram_id}:{sent.message_id}', reservation_id)
        except Exception:
            logger.exception('Failed to write reservation mapping into redis')


async def handle_list_my_reservations_archive_event(message):
    telegram_id = message.get('telegram_id')
    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            reservations = []
        else:
            res_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status.in_([ReservationStatus.COMPLETED, ReservationStatus.CANCELELLED])))
            reservations = res_q.scalars().all()

    from src.bot import bot
    for r in reservations:
        reservation_id = str(r.id)
        object_name = f"reservation/{reservation_id}.png"
        try:
            raw = images_storage.get_file(object_name)
        except Exception:
            raw = None

        if not raw:
            await bot.send_message(chat_id=telegram_id, text='QR-код не найден в хранилище.')
            text = (
                f"ID: {reservation_id}\n"
                f"Статус: {r.status.value}\n"
                f"Гостей: {r.people_quantity}\n"
                f"Класс: {r.room_class.value}\n"
                f"Заезд: {r.check_in_date}\n"
                f"Выезд: {r.eviction_date}\n"
            )
            await bot.send_message(chat_id=telegram_id, text=text)
            continue

        buf = io.BytesIO(raw)
        buf.seek(0)
        image_file = BufferedInputFile(file=buf.read(), filename=f'{reservation_id}_reservation_qr.png')

        caption = (
            f"ID: {reservation_id}\n"
            f"Статус: {r.status.value}\n"
            f"Гостей: {r.people_quantity}\n"
            f"Класс: {r.room_class.value}\n"
            f"Заезд: {r.check_in_date}\n"
            f"Выезд: {r.eviction_date}\n"
        )

        sent = await bot.send_photo(chat_id=telegram_id, photo=image_file, caption=caption)

        # store reverse mapping to allow clearing markups later
        try:
            from src.storage.redis import redis_storage
            import json
            member = {'telegram_id': telegram_id, 'message_id': sent.message_id}
            key = f'reservation:{reservation_id}:members'
            current_raw = await redis_storage.get(key)
            if current_raw:
                try:
                    current = json.loads(current_raw)
                except Exception:
                    current = []
            else:
                current = []
            current.append(member)
            await redis_storage.set(key, json.dumps(current))
            await redis_storage.set(f'reservation_message_map:{telegram_id}:{sent.message_id}', reservation_id)
        except Exception:
            logger.exception('Failed to write reservation mapping into redis')


async def handle_cancel_reservations_event(message):
    telegram_id = message.get('telegram_id')

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            resp = {'msg': 'Пользователь не найден'}
        else:
            # Only remove reservations with UNCONFIRM status. Do not delete IN_PROGRESS reservations.
            del_q = await db.execute(select(Reservation).filter(Reservation.user_id == user.id, Reservation.status == ReservationStatus.UNCONFIRM))
            reservations = del_q.scalars().all()
            if not reservations:
                resp = {'msg': 'Нет броней для удаления'}
            else:
                for r in reservations:
                    await db.delete(r)
                await db.commit()
                resp = {'msg': 'Ваши текущие брони удалены'}

    # send response directly to user instead of via RabbitMQ reply queue
    from src.bot import bot
    try:
        await bot.send_message(chat_id=telegram_id, text=resp.get('msg', ''))
    except Exception:
        logger.exception('Failed to send cancellation response to user')
    
    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(message.get('telegram_id'), clear_reservation_markups=False)
    except Exception:
        pass


async def handle_cancel_reservation_event(message):
    """Handle cancellation of a single reservation by id (sent from bot when user presses cancel_by_id)."""
    telegram_id = message.get('telegram_id')
    reservation_id = message.get('reservation_id')

    if not reservation_id:
        try:
            from src.bot import bot
            await bot.send_message(chat_id=telegram_id, text='Неполные данные для отмены брони')
        except Exception:
            logger.exception('Failed to send cancellation error')
        return

    # normalize uuid
    try:
        import uuid as _uuid
        if isinstance(reservation_id, str):
            reservation_id = _uuid.UUID(reservation_id)
    except Exception:
        pass

    async with async_session() as db:
        # find reservation for this user with UNCONFIRM status
        del_q = await db.execute(select(Reservation).filter(Reservation.id == reservation_id, Reservation.status == ReservationStatus.UNCONFIRM))
        reservation = del_q.scalar_one_or_none()
        if not reservation:
            resp = {'msg': 'Бронь не найдена или уже подтверждена'}
        else:
            await db.delete(reservation)
            await db.commit()
            resp = {'msg': 'Бронь удалена'}

    # from src.bot import bot
    # try:
    #     await bot.send_message(chat_id=telegram_id, text=resp.get('msg', ''))
    # except Exception:
    #     logger.exception('Failed to send cancellation response to user')

    # Attempt to delete the original reservation message if a message_id was provided
    try:
        from src.bot import bot
        message_id = message.get('message_id')
        if message_id:
            try:
                await bot.delete_message(chat_id=telegram_id, message_id=message_id)
            except Exception:
                pass
    except Exception:
        logger.exception('Failed to delete reservation message after cancellation')
