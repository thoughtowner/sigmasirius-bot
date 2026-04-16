from ..base import BaseMessage


class StartMessage(BaseMessage):
    telegram_id: int
    is_test_data: bool
    full_name: str
    phone_number: str
    flag: bool
