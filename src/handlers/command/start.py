from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message

from .router import router


class StartGroup(StatesGroup):
    first = State()
    second = State()


@router.message(Command('start'))
async def start_cmd(message: Message, state: FSMContext) -> None:
    print(await state.get_state())
    state_data = await state.get_state()

    if state_data == StartGroup.first:
        await state.set_state(StartGroup.second)
    else:
        await state.set_state(StartGroup.first)

    await message.answer('hello')
