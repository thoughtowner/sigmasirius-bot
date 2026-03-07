from ..base import BaseMessage


class ReservationMessage(BaseMessage):
    telegram_id: int
    full_name: str
    phone_number: str
    room: str
