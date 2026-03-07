from .model.models import User, ApplicationForm
from .schema.add_application_form import AddApplicationFormMessage

from consumers.application_form_consumer.storage.db import async_session
from sqlalchemy import select


def get_user(message: AddApplicationFormMessage) -> User:
    return User(
        telegram_id=message['telegram_id']
    )

async def get_application_form(message: AddApplicationFormMessage) -> ApplicationForm:
    async with async_session() as db:
        user_result = await db.execute(select(User.id).filter(User.telegram_id == message['telegram_id']))
        user_id = user_result.scalar()

    return ApplicationForm(
        title=message['title'],
        description=message['description'],
        status=ApplicationForm.Status(message['status']),
        user_id=user_id
    )
