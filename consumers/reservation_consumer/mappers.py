from .model.models import User, ApplicationForm
from .schema.reservation import ReservationMessage


def get_user(message: ReservationMessage) -> User:
    return User(
        telegram_id=message['telegram_id']
    )
