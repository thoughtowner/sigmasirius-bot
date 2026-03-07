from sqlalchemy import select, update

from src.model.models import User

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session

import asyncio
import logging

TELEGRAM_ID: int = 6244393260
PHONE_NUMBER: str = '+7 (999) 999-99-99'


async def add_roles(db: AsyncSession):
    user_result = await db.execute(
        select(User.id).filter(User.telegram_id == TELEGRAM_ID))
    user_id = user_result.scalar()

    if not user_id:
        print('User not found')
        return

    await db.execute(
        update(User).where(User.id == user_id).values(is_repairman=True, phone_number=PHONE_NUMBER)
    )
    await db.commit()

async def main():
    async with async_session() as db:
        await add_roles(db)

if __name__ == '__main__':
    asyncio.run(main())
