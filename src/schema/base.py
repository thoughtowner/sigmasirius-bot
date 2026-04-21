from typing import TypedDict


class BaseMessage(TypedDict):
    event: str
    is_test_data: bool = False
