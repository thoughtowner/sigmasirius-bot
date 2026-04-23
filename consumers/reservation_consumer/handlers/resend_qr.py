from config.settings import settings
from ..storage.db import async_session

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile
import io

from src.files_storage.storage_client import images_storage


default = DefaultBotProperties(parse_mode=ParseMode.HTML)


async def handle_resend_reservation_qr_event(message):
    """Resend stored reservation QR from object storage to the user.

    Expected message format: {'reservation_id': '<uuid>', 'telegram_id': <int>}
    """
    reservation_id = message.get('reservation_id')
    telegram_id = message.get('telegram_id')
    if not reservation_id or not telegram_id:
        return

    object_name = f"reservation/{reservation_id}.png"
    try:
        raw = images_storage.get_file(object_name)
    except Exception:
        raw = None

    # If file not found, notify user (do not regenerate)
    if not raw:
        from src.bot import bot
        await bot.send_message(chat_id=telegram_id, text='QR-код не найден в хранилище.')
        return

    buf = io.BytesIO(raw)
    buf.seek(0)
    image_file = BufferedInputFile(file=buf.read(), filename=f'{reservation_id}_reservation_qr.png')

    from src.bot import bot
    await bot.send_photo(chat_id=telegram_id, photo=image_file, caption='Ваш QR-код для заселения.')
