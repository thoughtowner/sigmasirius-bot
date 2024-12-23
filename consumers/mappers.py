from consumers.model.models import User, Role, ResidentAdditionalData, AdminAdditionalData, ApplicationForm, ApplicationFormStatus
from consumers.start_consumer.schema.start_data import StartData
from consumers.registration_consumer.schema.registration_data import RegistrationData
from consumers.add_application_form_consumer.schema.application_form_data import ApplicationFormData

from consumers.add_application_form_consumer.storage.db import async_session
from sqlalchemy import select


def from_start_data_to_user(start_data: StartData) -> User:
    return User(
        telegram_user_id=start_data['telegram_user_id'],
        telegram_user_username=start_data['telegram_user_username']
    )

def from_registration_data_to_user(registration_data: RegistrationData) -> User:
    return User(
        telegram_user_id=registration_data['telegram_user_id'],
        telegram_user_username=registration_data['telegram_user_username']
    )

def from_registration_data_to_resident_additional_data(registration_data: RegistrationData) -> ResidentAdditionalData:
    return ResidentAdditionalData(
        full_name=registration_data['full_name'],
        phone_number=registration_data['phone_number'],
        room=registration_data['room']
    )

def from_registration_data_to_admin_additional_data(registration_data: RegistrationData) -> AdminAdditionalData:
    return AdminAdditionalData(
        full_name=registration_data['full_name'],
        phone_number=registration_data['phone_number']
    )

def from_registration_data_to_role(registration_data: RegistrationData) -> Role:
    return Role(
        title=registration_data['role'],
    )

def from_application_form_data_to_user(application_form_data: ApplicationFormData) -> User:
    return User(
        telegram_user_id=application_form_data['telegram_user_id'],
        telegram_user_username=application_form_data['telegram_user_username']
    )

async def from_application_form_data_to_application_form(application_form_data: ApplicationFormData) -> ApplicationForm:
    async with async_session() as db:
        status_result = await db.execute(select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == application_form_data['status']))
        status_id = status_result.scalar()

        user_result = await db.execute(select(User.id).filter(User.telegram_user_id == application_form_data['telegram_user_id']))
        user_id = user_result.scalar()

    return ApplicationForm(
        title=application_form_data['title'],
        description=application_form_data['description'],
        status_id=status_id,
        user_id=user_id
    )
