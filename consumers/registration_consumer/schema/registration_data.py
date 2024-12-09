from typing import TypedDict

class RegistrationData(TypedDict):
    telegram_user_id: int
    role: str
    full_name: str
    phone_number: str
    room: str
