from .model.models import User, ApplicationForm, ApplicationFormStatus
from .schema.add_application_form import AddApplicationFormMessage

from consumers.application_form_consumer.storage.db import async_session
from sqlalchemy import select


def get_user(message: AddApplicationFormMessage) -> User:
    return User(
        telegram_id=message['telegram_id']
    )

async def get_application_form(message: AddApplicationFormMessage) -> ApplicationForm:
    async with async_session() as db:
        status_result = await db.execute(select(ApplicationFormStatus.id).filter(ApplicationFormStatus.title == message['status']))
        status_id = status_result.scalar()

        user_result = await db.execute(select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

    return ApplicationForm(
        title=message['title'],
        description=message['description'],
        status_id=status_id,
        user_id=user_id
    )
