from src.model.models import ApplicationFormStatus

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session

import asyncio
import logging


async def add_application_form_statuses(db: AsyncSession):
    new_application_form_statuses = [
        ApplicationFormStatus(title='not_completed'),
        ApplicationFormStatus(title='completed')
    ]
    db.add_all(new_application_form_statuses)
    await db.commit()

async def main():
    async with async_session() as db:
        await add_application_form_statuses(db)

if __name__ == '__main__':
    asyncio.run(main())
