from aiogram.fsm.state import StatesGroup, State


class AddApplicationForm(StatesGroup):
    title = State()
    description = State()
    photo = State()
