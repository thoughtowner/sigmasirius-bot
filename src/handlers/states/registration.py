from aiogram.fsm.state import StatesGroup, State


class Registration(StatesGroup):
    full_name = State()
    age = State()
    study_group = State()
    building = State()
    entrance = State()
    floor = State()
    room = State()
    phone_number = State()
