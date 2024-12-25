from typing import TypedDict


class ApplicationFormData(TypedDict):
    event: str
    action: str
    telegram_user_id: int
    telegram_user_username: str
    title: str
    description: str
    photo_title: str
    status: str
