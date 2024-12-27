from .base import BaseMessage


class AddApplicationFormMessage(BaseMessage):
    telegram_id: int
    title: str
    description: str
    photo_title: str
    status: str
