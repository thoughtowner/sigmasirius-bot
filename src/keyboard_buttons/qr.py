from aiogram.types import WebAppInfo, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import settings

def main_keyboard() -> InlineKeyboardMarkup:
    generate_url = settings.BASE_SITE
    kb = InlineKeyboardBuilder()
    kb.button(text="📷 Сканировать", web_app=WebAppInfo(url=f"{generate_url}/scan"))
    kb.button(text="📤 Загрузить QR", web_app=WebAppInfo(url=f"{generate_url}/upload"))
    kb.button(text="✨ Создать QR", web_app=WebAppInfo(url=f"{generate_url}"))
    kb.adjust(1)
    return kb.as_markup()
