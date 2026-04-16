from ..base import BaseMessage


class ReservationMessage(BaseMessage):
    telegram_id: int
    is_test_data: bool
    people_quantity: int
    room_class: str
    check_in_date: str
    eviction_date: str
