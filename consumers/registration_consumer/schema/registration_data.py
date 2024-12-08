from typing import TypedDict

class RegistrationData(TypedDict):
    user_id: int
    role: str
    full_name: str
    phone_number: str
    room: str
