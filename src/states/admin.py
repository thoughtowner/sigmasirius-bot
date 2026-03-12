from aiogram.fsm.state import StatesGroup, State


class AdminRepairman(StatesGroup):
    assign_phone = State()
    remove_phone = State()
