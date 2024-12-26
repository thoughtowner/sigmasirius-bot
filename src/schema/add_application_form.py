from .base import BaseMessage


class AddApplicationFormMessage(BaseMessage):
    action: str
    telegram_id: int
    title: str
    description: str
    photo_title: str
    status: str
