from sqlalchemy import select, insert, and_

from src.model.models import User, Role, UserRole, AdminAdditionalData

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session

import asyncio
import logging

TELEGRAM_ID: int = 6244393260
FULL_NAME: str = 'Example Full Name'
PHONE_NUMBER: str = '+7 (999) 999-99-99'


async def add_roles(db: AsyncSession):
    admin_role_result = await db.execute(select(Role.id).filter(Role.title == 'admin'))
    admin_role_id = admin_role_result.scalar()

    user_result = await db.execute(
        select(User.id).filter(User.telegram_id == TELEGRAM_ID))
    user_id = user_result.scalar()

    user_to_role_result = await db.execute(
        select(UserRole.id).filter(and_(UserRole.user_id == user_id, UserRole.role_id == admin_role_id)))
    user_to_role_id = user_to_role_result.scalar()

    if user_to_role_id:
        print('Пользователь уже является администратором.')
        return

    await db.execute(insert(UserRole).values(
        user_id=user_id,
        role_id=admin_role_id
    ))
    await db.flush()

    await db.execute(insert(AdminAdditionalData).values(
        full_name=FULL_NAME,
        phone_number=PHONE_NUMBER,
        user_id=user_id
    ))
    await db.commit()

async def main():
    async with async_session() as db:
        await add_roles(db)

if __name__ == '__main__':
    asyncio.run(main())
