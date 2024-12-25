import asyncio

import aio_pika
import msgpack
from aio_pika import ExchangeType
from aio_pika.exceptions import QueueEmpty
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config.settings import settings
from src.storage.rabbit import channel_pool
from ..router import router
from src.logger import logger

default = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=settings.BOT_TOKEN, default=default)

@router.callback_query(lambda callback_query: callback_query.data == 'cancel')
async def cancel(callback_query: CallbackQuery, state: FSMContext) -> None:
    telegram_user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    async with channel_pool.acquire() as channel:  # type: aio_pika.Channel
        logger.info('Send data to application_form queue...')

        async with channel_pool.acquire() as _channel:  # type: aio_pika.Channel
            application_form_for_admins_queue = await _channel.declare_queue('application_form_for_admins_queue',
                                                                             durable=True)
            unacked_messages = []

            retries = 3
            for _ in range(retries):
                try:
                    is_consume_needed_message_from_queue = False
                    while not is_consume_needed_message_from_queue:
                        try:
                            packed_application_form_for_admins_response_message = await application_form_for_admins_queue.get()
                            application_form_for_admins_response_message = msgpack.unpackb(packed_application_form_for_admins_response_message.body)

                            application_form_for_admins_data = application_form_for_admins_response_message['application_form_for_user_data']['admins']

                            for application_form_for_admin_data in application_form_for_admins_data:
                                if application_form_for_admin_data['chat_id'] == telegram_user_id and application_form_for_admin_data['message_id'] == message_id:
                                    await packed_application_form_for_admins_response_message.ack()
                                    is_consume_needed_message_from_queue = True
                                    break

                            if not is_consume_needed_message_from_queue:
                                unacked_messages.append(packed_application_form_for_admins_response_message)

                        except QueueEmpty:
                            pass

                except QueueEmpty:
                    await asyncio.sleep(1)
                finally:
                    if is_consume_needed_message_from_queue:
                        break

            if not is_consume_needed_message_from_queue:
                await callback_query.message.answer('Что-то пошло не так')

            for unacked_message in unacked_messages:
                await unacked_message.nack(requeue=True)

            application_form_for_owner_data = application_form_for_admins_response_message['application_form_for_user_data']['owner']
            application_form_id = application_form_for_admins_response_message['application_form_id']

        application_form_exchange = await channel.declare_exchange(settings.APPLICATION_FORM_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        application_form_queue = await channel.declare_queue(settings.APPLICATION_FORM_QUEUE_NAME, durable=True)
        await application_form_queue.bind(application_form_exchange, settings.APPLICATION_FORM_QUEUE_NAME)

        await application_form_exchange.publish(
            aio_pika.Message(
                msgpack.packb(
                    {
                        'event': 'application_form_new_status',
                        'action': 'complete',
                        'clicked_admin_telegram_user_id': telegram_user_id,
                        'clicked_admin_message_id': message_id,
                        'owner_telegram_user_id': application_form_for_owner_data['chat_id'],
                        'owner_message_id': application_form_for_owner_data['message_id'],
                        'application_form_id': application_form_id,
                        'new_status': 'cancelled',
                        'application_form_for_admins_response_message': application_form_for_admins_response_message
                    }
                ),
                # correlation_id=correlation_id_ctx.get()
            ),
            settings.APPLICATION_FORM_QUEUE_NAME
        )
