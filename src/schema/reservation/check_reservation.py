from ..base import BaseMessage


class CheckReservationMessage(BaseMessage):
    telegram_id: int
    is_test_data=False,
