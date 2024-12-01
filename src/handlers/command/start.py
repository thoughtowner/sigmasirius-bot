from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .router import router
from ..states.auth import AuthGroup


@router.message(Command('start'))
async def start_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(AuthGroup.no_authorized)
    await message.answer('Hello!')


@router.message()
async def start_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(AuthGroup.authorized)
    await message.answer('Hello asdasd!')
