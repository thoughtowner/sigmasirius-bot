from consumers.model.user import User, UserStatus
from consumers.registration_consumer.schema.registration import RegistrationData


def from_parsed_registration_data(registration_data: RegistrationData) -> User:
    return User(
        full_name=registration_data['name'],
        age=int(registration_data['age']),
        study_group=registration_data['study_group'],
        room=registration_data['room'],
        phone_number=registration_data['phone_number'],
        telegram_id=registration_data['user_id'],
        status=UserStatus.NO_ACTIVE
    )
