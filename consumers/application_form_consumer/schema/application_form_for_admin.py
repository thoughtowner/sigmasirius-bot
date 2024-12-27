from typing import TypedDict


class ApplicationFormForAdminMessage(TypedDict):
    title: str
    description: str
    status: str
    resident_full_name: str
    resident_phone_number: str
    resident_room: str
