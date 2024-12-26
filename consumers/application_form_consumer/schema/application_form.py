from .base import BaseMessage


class ApplicationFormMessage(BaseMessage):
    action: str
    telegram_id: int
    title: str
    description: str
    photo_title: str
    status: str
