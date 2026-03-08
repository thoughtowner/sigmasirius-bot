from aiogram.fsm.state import StatesGroup, State


class Reservation(StatesGroup):
    people_quantity = State()
    room_class = State()
    check_in_date = State()
    eviction_date = State()
    check_reservation_data = State()
