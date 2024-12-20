from typing import TypedDict


class ApplicationFormForAdminsData(TypedDict):
    telegram_user_id: int
    title: str
    description: str
    status: str
    application_form_id: str
    resident_full_name: str
    resident_phone_number: str
    resident_room: str
