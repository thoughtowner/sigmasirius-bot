from aiogram import F
from aiogram.types import CallbackQuery
from ..router import router
from src.storage.rabbit import channel_pool
import aio_pika
from config.settings import settings
import msgpack
from aio_pika import ExchangeType


@router.callback_query(F.data == 'resident_cancel_application')
async def resident_cancel_published_application(query: CallbackQuery):
    await query.answer()
    # send request to consumer to delete application by mapping from message_map
    payload = {
        'event': 'change_application_form_status',
        'action': 'resident_cancel_application',
        'telegram_id': query.from_user.id,
        'message_id': query.message.message_id,
    }

    async with channel_pool.acquire() as channel:
        application_form_exchange = await channel.declare_exchange(settings.APPLICATION_FORM_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        application_form_queue = await channel.declare_queue(settings.APPLICATION_FORM_QUEUE_NAME, durable=True)
        await application_form_queue.bind(application_form_exchange, settings.APPLICATION_FORM_QUEUE_NAME)
        await application_form_exchange.publish(
            aio_pika.Message(msgpack.packb(payload)),
            settings.APPLICATION_FORM_QUEUE_NAME
        )

    # delete resident-facing message and show start inline keyboard
    try:
        await query.message.delete()
    except Exception:
        pass

    try:
        from consumers.start_consumer.handlers.start import send_reply_start_keyboard
        await send_reply_start_keyboard(query.from_user.id)
    except Exception:
        pass
