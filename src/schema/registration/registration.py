from ..base import BaseMessage


class RegistrationMessage(BaseMessage):
    telegram_id: int
    full_name: str
    phone_number: str
    room: str
