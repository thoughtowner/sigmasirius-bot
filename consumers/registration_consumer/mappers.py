from .model.models import User, Role, ResidentAdditionalData, AdminAdditionalData, ApplicationForm, ApplicationFormStatus
from .schema.registration import RegistrationMessage


def get_user(message: RegistrationMessage) -> User:
    return User(
        telegram_id=message['telegram_id']
    )

def get_resident_additional_data(message: RegistrationMessage) -> ResidentAdditionalData:
    return ResidentAdditionalData(
        full_name=message['full_name'],
        phone_number=message['phone_number'],
        room=message['room']
    )

def get_admin_additional_data(message: RegistrationMessage) -> AdminAdditionalData:
    return AdminAdditionalData(
        full_name=message['full_name'],
        phone_number=message['phone_number']
    )
