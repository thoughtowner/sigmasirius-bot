from aiogram.fsm.state import StatesGroup, State


class AuthGroup(StatesGroup):
    no_authorized = State()
    authorized = State()
