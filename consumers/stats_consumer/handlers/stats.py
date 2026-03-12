from src.storage.db import async_session
from src.model.models import ApplicationForm, ApplicationFormStatus, TelegramIdAndMessageId, User
from sqlalchemy import select, func
from config.settings import settings
import aio_pika
import msgpack
from aio_pika import ExchangeType
from src.storage.rabbit import channel_pool
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from ..logger import LOGGING_CONFIG, logger
from datetime import date

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

async def handle_admin_stats_event(message):
    admin_id = message.get('telegram_id')

    async with async_session() as db:
        total_q = await db.execute(select(func.count()).select_from(ApplicationForm))
        total = total_q.scalar() or 0

        completed_q = await db.execute(select(func.count()).select_from(ApplicationForm).where(ApplicationForm.status == ApplicationFormStatus.COMPLETED))
        completed = completed_q.scalar() or 0

        cancelled_q = await db.execute(select(func.count()).select_from(ApplicationForm).where(ApplicationForm.status == ApplicationFormStatus.CANCELELLED))
        cancelled = cancelled_q.scalar() or 0

        awaiting_q = await db.execute(select(func.count()).select_from(ApplicationForm).where(ApplicationForm.status == ApplicationFormStatus.NOT_COMPLETED))
        awaiting = awaiting_q.scalar() or 0

        # per-repairman stats
        repairmen_q = await db.execute(select(User).where(User.is_repairman == True))
        repairmen = repairmen_q.scalars().all()

        per_rs = []
        for r in repairmen:
            # count completed forms associated with this repairman via TelegramIdAndMessageId
            comp_q = await db.execute(
                select(func.count()).select_from(ApplicationForm).join(TelegramIdAndMessageId, TelegramIdAndMessageId.application_form_id == ApplicationForm.id).where(
                    (ApplicationForm.status == ApplicationFormStatus.COMPLETED) & (TelegramIdAndMessageId.telegram_id == r.telegram_id)
                )
            )
            comp_count = comp_q.scalar() or 0
            days_worked = (date.today() - r.got_role_from_date).days if getattr(r, 'got_role_from_date', None) else 0
            per_rs.append({'name': r.full_name, 'completed': comp_count, 'days': days_worked})

    text_lines = [
        f"Всего заявок: {total}",
        f"Выполнено: {completed}",
        f"Отменено: {cancelled}",
        f"Ожидающих: {awaiting}",
        "",
        "Статистика по ремонтникам:"
    ]
    for pr in per_rs:
        text_lines.append(f"{pr['name']}: выполнено {pr['completed']}, отработано дней {pr['days']}")

    text = "\n".join(text_lines)

    async with channel_pool.acquire() as channel:
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        queue_name = settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=admin_id)
        reverse_queue = await channel.declare_queue(queue_name, durable=True)
        await reverse_queue.bind(start_exchange, queue_name)
        await start_exchange.publish(aio_pika.Message(msgpack.packb({'text': text})), queue_name)


async def handle_repairman_stats_event(message):
    telegram_id = message.get('telegram_id')

    async with async_session() as db:
        user_q = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = user_q.scalar_one_or_none()
        if not user:
            text = 'Пользователь не найден'
        else:
            comp_q = await db.execute(
                select(func.count()).select_from(ApplicationForm).join(TelegramIdAndMessageId, TelegramIdAndMessageId.application_form_id == ApplicationForm.id).where(
                    (ApplicationForm.status == ApplicationFormStatus.COMPLETED) & (TelegramIdAndMessageId.telegram_id == telegram_id)
                )
            )
            comp_count = comp_q.scalar() or 0
            days_worked = (date.today() - user.got_role_from_date).days if getattr(user, 'got_role_from_date', None) else 0
            text = f"Выполнено заявок: {comp_count}\nОтработано дней: {days_worked}"

    async with channel_pool.acquire() as channel:
        start_exchange = await channel.declare_exchange(settings.START_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        queue_name = settings.USER_CHECK_START_QUEUE_TEMPLATE.format(telegram_id=telegram_id)
        reverse_queue = await channel.declare_queue(queue_name, durable=True)
        await reverse_queue.bind(start_exchange, queue_name)
        await start_exchange.publish(aio_pika.Message(msgpack.packb({'text': text})), queue_name)
