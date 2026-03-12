from ..base import BaseMessage


class CheckPhoneNumberMessage(BaseMessage):
    telegram_id: int
    phone_number: str
