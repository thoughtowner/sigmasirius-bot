import logging.config

import aio_pika
import msgpack

from .logger import LOGGING_CONFIG, logger, correlation_id_ctx
from .storage.rabbit import channel_pool

from .mappers import get_user
from config.settings import settings
from .storage.db import async_session

from aio_pika import ExchangeType
from sqlalchemy.exc import IntegrityError

from .model.models import User
from sqlalchemy import select, insert

from .metrics import TOTAL_RECEIVED_MESSAGES

from .handlers.reservation import handle_reservation_event
from .handlers.check_unconfirmed_reservation import handle_check_unconfirmed_reservation_event
from .handlers.pick_and_assign import handle_pick_room_event, handle_assign_room_event
from .handlers.manage_list_cancel import (
    handle_list_my_reservations_event,
    handle_list_my_reservations_archive_event,
    handle_cancel_reservations_event,
    handle_cancel_reservation_event,
)


async def reservation_consumer() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    logger.info('Starting reservation consumer...')

    async with channel_pool.acquire() as channel:

        await channel.set_qos(prefetch_count=10)

        reservation_queue = await channel.declare_queue(settings.RESERVATION_QUEUE_NAME, durable=True)

        logger.info('reservation consumer started!')
        async with reservation_queue.iterator() as queue_iter:
            async for message in queue_iter: # type: aio_pika.Message
                TOTAL_RECEIVED_MESSAGES.inc()
                async with message.process():
                    # correlation_id_ctx.set(message.correlation_id)

                    body = msgpack.unpackb(message.body)
                    logger.info("Received message %s", body)

                    if body['event'] == 'reservation':
                        await handle_reservation_event(body)
                    elif body['event'] == 'check_unconfirmed_reservation':
                        await handle_check_unconfirmed_reservation_event(body)
                    elif body['event'] == 'list_my_reservations':
                        await handle_list_my_reservations_event(body)
                    elif body['event'] == 'list_my_reservations_archive':
                        await handle_list_my_reservations_archive_event(body)
                    elif body['event'] == 'cancel_reservations':
                        await handle_cancel_reservations_event(body)
                    elif body['event'] == 'cancel_reservation':
                        await handle_cancel_reservation_event(body)

                    elif body['event'] == 'pick_room':
                        await handle_pick_room_event(body)
                    elif body['event'] == 'assign_room':
                        await handle_assign_room_event(body)
