# from fastapi import APIRouter


# router = APIRouter()


import base64
from aiogram.types import BufferedInputFile
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from src.api.tg.schemas import QRCodeRequest, QRCodeScanner
from src.bot import bot
from src.keyboard_buttons.qr import main_keyboard
from src.storage.rabbit import channel_pool
import aio_pika
from aio_pika import ExchangeType
import msgpack
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.keyboard_buttons.reservation import ROOM_CLASSES_ROW_BUTTONS
from src.logger import LOGGING_CONFIG, logger
import logging.config
from aio_pika.exceptions import QueueEmpty
import asyncio
from sqlalchemy import select
from src.storage.db import async_session
from src.model.models import Reservation, ReservationStatus, User
from pydantic import BaseModel
from datetime import date
from config.settings import settings


router = APIRouter(prefix='', tags=['API'])


class UserCheck(BaseModel):
    user_id: int


@router.post("/check-scanner-permissions/", response_class=JSONResponse)
async def check_scanner_permissions(request: UserCheck):
    """Return whether given Telegram user may use the scanner: must be registered (ran /start) and be admin."""
    try:
        telegram_id = int(request.user_id)
        async with async_session() as db:
            user_result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
            user = user_result.scalar()

            if not user:
                return JSONResponse(content={"allowed": False, "message": "Перед использованием выполните /start"}, status_code=200)

            if not user.is_admin:
                return JSONResponse(content={"allowed": False, "message": "Только администратор может использовать сканер"}, status_code=200)

            return JSONResponse(content={"allowed": True, "message": "OK"}, status_code=200)
    except Exception as e:
        print(f"[check-scanner-permissions] exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# @router.post("/send-scaner-info/", response_class=JSONResponse)
# async def send_qr_code(request: QRCodeScanner):
#     try:
#         # debug: log incoming payload
#         print(f"[send-scaner-info] incoming: user_id={request.user_id} result_len={len(request.result_scan) if request.result_scan is not None else 0}")

#         text = (
#             f"🎉 QR-код успешно отсканирован!\n\n"
#             f"📄 Результат сканирования:\n\n"
#             f"<code><b>{request.result_scan}</b></code>\n\n"
#             f"🔗 Если это ссылка, вы можете перейти по ней.\n"
#             f"📝 Если это текст, вы можете скопировать его для дальнейшего использования.\n\n"
#             f"Что бы вы хотели сделать дальше? 👇"
#         )
#         try:
#             await bot.send_message(chat_id=request.user_id, text=text, reply_markup=main_keyboard())
#         except Exception as send_err:
#             print(f"[send-scaner-info] bot.send_message error: {send_err}")
#             raise

#         return JSONResponse(content={"message": "QR-код успешно просканирован, а данные отправлены в Telegram"},
#                               status_code=200)
#     except Exception as e:
#         print(f"[send-scaner-info] exception: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post("/check-unconfirmed-reservation/", response_class=JSONResponse)
# async def check_unconfirmed_reservation(request: QRCodeScanner):
#     """Called by admin WebApp after scanning QR. Publishes a check_unconfirmed_reservation event to reservation exchange.
#     Expects `result_scan` contain the QR content like 'reservation/<uuid>' and `user_id` be admin telegram id.
#     """
#     try:
#         qr = request.result_scan or ''
#         admin_id = request.user_id
#         # extract reservation id if prefixed
#         reservation_id = None
#         if qr.startswith('reservation/'):
#             reservation_id = qr.split('/', 1)[1]
#         else:
#             reservation_id = qr

#         payload = {
#             'event': 'check_unconfirmed_reservation',
#             'reservation_id': str(reservation_id),
#             'telegram_id': int(admin_id)
#         }

#         async with channel_pool.acquire() as channel:
#             reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
#             # publish to reservation queue routing key
#             await reservation_exchange.publish(
#                 aio_pika.Message(msgpack.packb(payload)),
#                 settings.RESERVATION_QUEUE_NAME
#             )

#         return JSONResponse(content={"message": "Запрос проверки брони отправлен"}, status_code=200)
#     except Exception as e:
#         print(f"[check-unconfirmed-reservation] exception: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm-reservation/", response_class=JSONResponse)
async def confirm_reservation(request: QRCodeScanner):
    """Publish check_unconfirmed_reservation and wait for consumer reply, then notify admin via bot message.
    This mirrors the bot handler flow but is triggered from the WebApp.
    """
    try:
        qr = request.result_scan
        admin_id = int(request.user_id)
        reservation_id = qr.split('/', 1)[1] if qr.startswith('reservation/') else qr

        # publish check request
        payload = {
            'event': 'check_unconfirmed_reservation',
            'reservation_id': str(reservation_id),
            'telegram_id': admin_id
        }
        async with channel_pool.acquire() as channel:
            reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            await reservation_exchange.publish(
                aio_pika.Message(msgpack.packb(payload)),
                settings.RESERVATION_QUEUE_NAME
            )

        print(f"[api] confirm_reservation received qr={qr} admin_id={admin_id} reservation_id={reservation_id}")
        # wait for response on admin queue
        async with channel_pool.acquire() as channel:
            user_reservation_queue = await channel.declare_queue(
                settings.USER_RESERVATION_QUEUE_TEMPLATE.format(telegram_id=admin_id),
                durable=True,
            )

            retries = 10
            body = None
            for _ in range(retries):
                try:
                    reservation_response_message = await user_reservation_queue.get(no_ack=True)
                    body = msgpack.unpackb(reservation_response_message.body)
                    print(f"[api] confirm_reservation got message from queue: {body}")
                    break
                except Exception:
                    await asyncio.sleep(1)

        if not body or not body.get('found'):
            # inform admin via bot and respond to webapp
            try:
                await bot.send_message(admin_id, 'Не найдено неподтверждённых броней по этому QR-коду или бронь не на сегодня.')
            except Exception:
                pass
            return JSONResponse(content={"message": "Бронь не найдена"}, status_code=404)

        reservation = body['reservation']
        res_text = (
            f"Бронь ID: {reservation['id']}\n"
            f"Количество человек: {reservation['people_quantity']}\n"
            f"Класс номера: {reservation['room_class']}\n"
            f"Дата заезда: {reservation['check_in_date']}\n"
            f"Дата выезда: {reservation['eviction_date']}\n"
        )

        pick_btn = InlineKeyboardButton(text='Подобрать номер', callback_data=f'pick_room:{reservation["id"]}')
        kb = InlineKeyboardMarkup(inline_keyboard=[[pick_btn]])

        try:
            await bot.send_message(admin_id, res_text, reply_markup=kb)
        except Exception as send_err:
            print(f"[confirm-reservation] bot.send_message error: {send_err}")

        return JSONResponse(content={"message": "Бронь найдена и отправлена администратору"}, status_code=200)
    except Exception as e:
        print(f"[confirm-reservation] exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assign-repairman/", response_class=JSONResponse)
async def confirm_repairman(request: QRCodeScanner):
    """...
    """
    try:
        qr = request.result_scan
        admin_id = int(request.user_id)
        repairman_id = qr.split('/', 1)[1] if qr.startswith('repairman/') else qr

        # publish check request
        payload = {
            'event': 'assign_repairman',
            'repairman_id': str(repairman_id),
            'telegram_id': admin_id
        }
        async with channel_pool.acquire() as channel:
            repairman_exchange = await channel.declare_exchange(settings.REPAIRMAN_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            await repairman_exchange.publish(
                aio_pika.Message(msgpack.packb(payload)),
                settings.REPAIRMAN_QUEUE_NAME
            )

        print(f"[api] confirm_repairman received qr={qr} admin_id={admin_id} repairman_id={repairman_id}")
        # wait for response on admin queue
        async with channel_pool.acquire() as channel:
            user_repairman_queue = await channel.declare_queue(
                settings.USER_REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id),
                durable=True,
            )

            retries = 10
            body = None
            for _ in range(retries):
                try:
                    repairman_response_message = await user_repairman_queue.get(no_ack=True)
                    body = msgpack.unpackb(repairman_response_message.body)
                    print(f"[api] confirm_repairman got message from queue: {body}")
                    break
                except Exception:
                    await asyncio.sleep(1)

        if not body.get('found'):
            # inform admin via bot and respond to webapp
            try:
                reason = body.get('reason')
                if reason == 'not_found':
                    await bot.send_message(admin_id, 'Пользователь не найден.')
                elif reason == 'repairman':
                    await bot.send_message(admin_id, 'Пользователь уже является работником.')
                elif reason == 'admin':
                    await bot.send_message(admin_id, 'Пользователь является администратором. Пользователь не может иметь несколько ролей.')
            except Exception:
                pass
            return JSONResponse(content={"message": "Бронь не найдена"}, status_code=404)

        try:
            await bot.send_message(admin_id, "Ремонтник успешно принят на работу!")
        except Exception as send_err:
            print(f"[confirm-repairman] bot.send_message error: {send_err}")

        return JSONResponse(content={"message": "Ремонтник найден и принят на работу"}, status_code=200)
    except Exception as e:
        print(f"[confirm-repairman] exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/fire-repairman/", response_class=JSONResponse)
async def fire_repairman(request: QRCodeScanner):
    """...
    """
    try:
        qr = request.result_scan
        admin_id = int(request.user_id)
        repairman_id = qr.split('/', 1)[1] if qr.startswith('quit_as_repairman/') else qr

        # publish check request
        payload = {
            'event': 'fire_repairman',
            'repairman_id': str(repairman_id),
            'telegram_id': admin_id
        }
        async with channel_pool.acquire() as channel:
            repairman_exchange = await channel.declare_exchange(settings.REPAIRMAN_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            await repairman_exchange.publish(
                aio_pika.Message(msgpack.packb(payload)),
                settings.REPAIRMAN_QUEUE_NAME
            )

        print(f"[api] fire_repairman received qr={qr} admin_id={admin_id} repairman_id={repairman_id}")
        # wait for response on admin queue
        async with channel_pool.acquire() as channel:
            user_repairman_queue = await channel.declare_queue(
                settings.USER_REPAIRMAN_QUEUE_TEMPLATE.format(telegram_id=admin_id),
                durable=True,
            )

            retries = 10
            body = None
            for _ in range(retries):
                try:
                    repairman_response_message = await user_repairman_queue.get(no_ack=True)
                    body = msgpack.unpackb(repairman_response_message.body)
                    print(f"[api] fire_repairman got message from queue: {body}")
                    break
                except Exception:
                    await asyncio.sleep(1)

        if not body.get('found'):
            # inform admin via bot and respond to webapp
            try:
                reason = body.get('reason')
                if reason == 'not_found':
                    await bot.send_message(admin_id, 'Пользователь не найден.')
                elif reason == 'repairman':
                    await bot.send_message(admin_id, 'Пользователь не является работником.')
            except Exception:
                pass
            return JSONResponse(content={"message": "Бронь не найдена"}, status_code=404)

        try:
            await bot.send_message(admin_id, "Ремонтник успешно уволен с должности ремонтника!")
        except Exception as send_err:
            print(f"[confirm-repairman] bot.send_message error: {send_err}")

        return JSONResponse(content={"message": "Ремонтник найден и уволен с должности ремонтника"}, status_code=200)
    except Exception as e:
        print(f"[confirm-repairman] exception: {e} {body}")
        raise HTTPException(status_code=500, detail=str(e))
