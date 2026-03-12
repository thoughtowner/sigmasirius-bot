from sqlalchemy import select, update
from datetime import date

from src.model.models import User

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session

import asyncio
import logging

PHONE_NUMBER: str = '+7 (999) 999-99-99'


async def add_user_admin_role(db: AsyncSession):
    user_result = await db.execute(
        select(User.id).filter(User.phone_number == PHONE_NUMBER))
    user_id = user_result.scalar()

    if not user_id:
        print('Пользователь не найден!')
        return

    await db.execute(
        update(User).where(User.id == user_id).values(is_admin=True, got_role_from_date=date.today())
    )
    await db.commit()

    print('Пользователь успешно стал администратором')

async def main():
    async with async_session() as db:
        await add_user_admin_role(db)

if __name__ == '__main__':
    asyncio.run(main())
