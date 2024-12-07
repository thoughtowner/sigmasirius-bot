from consumers.model.user import User
from consumers.registration_consumer.schema.registration_data import RegistrationData


def from_parsed_registration_data_to_user(registration_data: RegistrationData) -> User:
    return User(
        full_name=registration_data['full_name'],
        age=int(registration_data['age']),
        study_group=registration_data['study_group'],
        room=registration_data['room'],
        phone_number=registration_data['phone_number'],
        telegram_id=registration_data['user_id']
    )
