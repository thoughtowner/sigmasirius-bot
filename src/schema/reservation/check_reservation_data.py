from typing import TypedDict


class CheckReservationDataMessage(TypedDict):
    people_quantity: int
    room_class: str
    check_in_date: str
    eviction_date: str
