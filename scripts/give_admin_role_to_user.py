from sqlalchemy import select, insert

from src.model.models import User, Role, UserRole

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session

import asyncio
import logging


async def add_roles(db: AsyncSession):
    admin_role_result = await db.execute(select(Role.id).filter(Role.title == 'admin'))
    admin_role_id = admin_role_result.scalar()

    user_result = await db.execute(
        select(User.id).filter(User.telegram_user_id == 785561828))
    user_id = user_result.scalar()

    user_role_query = insert(UserRole).values(
        user_id=user_id,
        role_id=admin_role_id,
    )

    await db.execute(user_role_query)
    await db.commit()

async def main():
    async with async_session() as db:
        await add_roles(db)

if __name__ == '__main__':
    asyncio.run(main())
