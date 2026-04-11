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
from src.storage.db import async_session
from src.model.models import Reservation, ReservationStatus
from datetime import date
from config.settings import settings


router = APIRouter(prefix='', tags=['API'])

@router.post("/send-qr/", response_class=JSONResponse)
async def send_qr_code(request: QRCodeRequest):
    try:
        # Получаем base64 строку из запроса
        base64_data = request.qr_code_url

        # Удаляем префикс MIME, если он есть
        if base64_data.startswith('data:image/'):
            base64_data = base64_data.split(',', 1)[1]

        # Декодируем base64 изображение в байты
        image_data = base64.b64decode(base64_data)

        # Создаем BufferedInputFile для отправки изображения
        image_file = BufferedInputFile(file=image_data, filename="qr_code.png")

        caption = (
            "🎉 Ваш QR-код успешно создан и отправлен!\n\n"
            "🔍 Вы можете отсканировать его, чтобы проверить содержимое.\n"
            "📤 Поделитесь этим QR-кодом с другими или сохраните его для дальнейшего использования.\n\n"
            "Что бы вы хотели сделать дальше? 👇"
        )

        # Используем BufferedInputFile для отправки изображения
        await bot.send_photo(
            chat_id=request.user_id,
            photo=image_file,  # Передаем BufferedInputFile
            caption=caption,
            reply_markup=main_keyboard()
        )

        return JSONResponse(content={"message": "QR-код успешно отправлен"}, status_code=200)
    except Exception as e:
        print(f"Ошибка при отправке QR-кода: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке QR-кода: {str(e)}")
    
@router.post("/send-scaner-info/", response_class=JSONResponse)
async def send_qr_code(request: QRCodeScanner):
    try:
        # debug: log incoming payload
        print(f"[send-scaner-info] incoming: user_id={request.user_id} result_len={len(request.result_scan) if request.result_scan is not None else 0}")

        text = (
            f"🎉 QR-код успешно отсканирован!\n\n"
            f"📄 Результат сканирования:\n\n"
            f"<code><b>{request.result_scan}</b></code>\n\n"
            f"🔗 Если это ссылка, вы можете перейти по ней.\n"
            f"📝 Если это текст, вы можете скопировать его для дальнейшего использования.\n\n"
            f"Что бы вы хотели сделать дальше? 👇"
        )
        try:
            await bot.send_message(chat_id=request.user_id, text=text, reply_markup=main_keyboard())
        except Exception as send_err:
            print(f"[send-scaner-info] bot.send_message error: {send_err}")
            raise

        return JSONResponse(content={"message": "QR-код успешно просканирован, а данные отправлены в Telegram"},
                              status_code=200)
    except Exception as e:
        print(f"[send-scaner-info] exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-unconfirmed-reservation/", response_class=JSONResponse)
async def check_unconfirmed_reservation(request: QRCodeScanner):
    """Called by admin WebApp after scanning QR. Publishes a check_unconfirmed_reservation event to reservation exchange.
    Expects `result_scan` contain the QR content like 'reservation/<uuid>' and `user_id` be admin telegram id.
    """
    try:
        qr = request.result_scan or ''
        admin_id = request.user_id
        # extract reservation id if prefixed
        reservation_id = None
        if qr.startswith('reservation/'):
            reservation_id = qr.split('/', 1)[1]
        else:
            reservation_id = qr

        payload = {
            'event': 'check_unconfirmed_reservation',
            'reservation_id': str(reservation_id),
            'telegram_id': int(admin_id)
        }

        async with channel_pool.acquire() as channel:
            reservation_exchange = await channel.declare_exchange(settings.RESERVATION_EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
            # publish to reservation queue routing key
            await reservation_exchange.publish(
                aio_pika.Message(msgpack.packb(payload)),
                settings.RESERVATION_QUEUE_NAME
            )

        return JSONResponse(content={"message": "Запрос проверки брони отправлен"}, status_code=200)
    except Exception as e:
        print(f"[check-unconfirmed-reservation] exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
