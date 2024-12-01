from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, \
    InlineKeyboardMarkup

from .router import router
from ..states.auth import AuthGroup


@router.message(Command('start'))
async def start_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(AuthGroup.no_authorized)

    await state.set_data({
        'button1': 1,
        'button2': 1,
    })

    # callback buttons
    inline_btn_1 = InlineKeyboardButton(text='Первая кнопка!', callback_data='button1')
    inline_btn_2 = InlineKeyboardButton(text='Вторая кнопка!', callback_data='button2')
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[inline_btn_1, inline_btn_2]]
    )

    # text buttons
    # button1 = KeyboardButton(text='1️⃣')
    # button2 = KeyboardButton(text='2️⃣')
    # button3 = KeyboardButton(text='3️⃣')
    # markup = ReplyKeyboardMarkup(keyboard=[[button1, button2, button3]])

    await message.answer('Hello!', reply_markup=markup)


@router.message()
async def start_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(AuthGroup.authorized)
    await message.answer('Hello asdasd!')
