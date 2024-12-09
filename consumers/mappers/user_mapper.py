from consumers.model.models import User, Role, ResidentAdditionalData, ApplicationForm
from consumers.registration_consumer.schema.registration_data import RegistrationData


def from_registration_data_to_user(registration_data: RegistrationData) -> User:
    return User(
        telegram_user_id=registration_data['telegram_user_id'],
        full_name=registration_data['full_name'],
        phone_number=registration_data['phone_number']
    )

def from_registration_data_to_resident_additional_data(registration_data: RegistrationData) -> ResidentAdditionalData:
    return ResidentAdditionalData(
        room=registration_data['room']
    )

def from_registration_data_to_role(registration_data: RegistrationData) -> Role:
    return Role(
        title=registration_data['role'],
    )