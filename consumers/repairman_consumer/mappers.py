from .model.models import User, ApplicationForm
from .schema.repairman import RepairmanMessage
from .storage.db import async_session

from sqlalchemy import select


def get_user(message: RepairmanMessage) -> User:
    return User(
        telegram_id=message['telegram_id']
    )
