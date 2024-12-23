from typing import TypedDict


class RegistrationData(TypedDict):
    telegram_user_id: int
    telegram_user_username: str
    full_name: str
    phone_number: str
    room: str
