from typing import TypedDict

from consumers.model.models import ApplicationFormStatus


class ApplicationFormData(TypedDict):
    telegram_user_id: int
    title: str
    description: str
    photo: str
    status: str
