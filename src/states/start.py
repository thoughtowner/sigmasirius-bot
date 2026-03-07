from aiogram.fsm.state import StatesGroup, State


class Start(StatesGroup):
    full_name = State()
    phone_number = State()
