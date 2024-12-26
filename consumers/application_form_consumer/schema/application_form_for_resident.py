from .base import BaseMessage


class ApplicationFormForAdminMessage(BaseMessage):
    action: str
    telegram_id: int
    title: str
    description: str
    status: str
    application_form_id: str
