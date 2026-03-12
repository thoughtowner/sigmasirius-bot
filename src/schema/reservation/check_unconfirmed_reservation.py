from ..base import BaseMessage


class CheckUnconfirmedReservationMessage(BaseMessage):
    phone_number: str
    telegram_id: int
