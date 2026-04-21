from .base import BaseMessage


class RepairmanMessage(BaseMessage):
    action: str
    telegram_id: int
