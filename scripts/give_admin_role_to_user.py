from sqlalchemy import select, insert, update

from src.model.models import User, Role, UserRole

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session

import asyncio
import logging

TELEGRAM_ID = 6244393260


async def add_roles(db: AsyncSession, telegram_id: int):
    admin_role_result = await db.execute(select(Role.id).filter(Role.title == 'admin'))
    admin_role_id = admin_role_result.scalar()

    user_result = await db.execute(
        select(User.id).filter(User.telegram_id == telegram_id))
    user_id = user_result.scalar()

    await db.execute(insert(UserRole).values(
        user_id=user_id,
        role_id=admin_role_id
    ))
    await db.commit()

async def main(telegram_id: int):
    async with async_session() as db:
        await add_roles(db, telegram_id)

if __name__ == '__main__':
    asyncio.run(main(TELEGRAM_ID))
