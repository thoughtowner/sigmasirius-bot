from ..base import BaseMessage


class StartMessage(BaseMessage):
    telegram_id: int
    full_name: str
    phone_number: str
    flag: bool
