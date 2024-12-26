from .model.models import User, Role, ResidentAdditionalData, AdminAdditionalData, ApplicationForm, ApplicationFormStatus
from .schema.start import StartMessage
from .storage.db import async_session

from sqlalchemy import select


def get_user(message: StartMessage) -> User:
    return User(
        telegram_id=message['telegram_id']
    )
