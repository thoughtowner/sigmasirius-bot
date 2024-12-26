from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

from ..router import router
from src.commands import GET_MY_TELEGRAM_ID


@router.message(F.text == GET_MY_TELEGRAM_ID)
async def get_my_telegram_id(message: Message, state: FSMContext):
    await message.answer(f'Ваш telegram_id: {message.from_user.id}')
