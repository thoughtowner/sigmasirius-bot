from .model.models import User, Resident, ApplicationForm
from .schema.reservation import ReservationMessage


def get_user(message: ReservationMessage) -> User:
    return User(
        telegram_id=message['telegram_id']
    )

def get_resident(message: ReservationMessage) -> Resident:
    return Resident(
        full_name=message['full_name'],
        room=message['room']
    )
