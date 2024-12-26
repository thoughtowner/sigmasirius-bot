from .base import BaseMessage


class StartMessage(BaseMessage):
    action: str
    telegram_id: int
