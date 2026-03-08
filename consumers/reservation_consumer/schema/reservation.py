from .base import BaseMessage


class ReservationMessage(BaseMessage):
    telegram_id: int
    full_name: str
    phone_number: str
    people_quantity: int
    room_class: str
    check_in_date: str
    eviction_date: str
