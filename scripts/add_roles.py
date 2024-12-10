from src.model.models import Role

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session

import asyncio
import logging


async def add_roles(db: AsyncSession):
    new_roles = [
        Role(title='resident'),
        Role(title='admin')
    ]
    db.add_all(new_roles)
    await db.commit()

async def main():
    async with async_session() as db:
        await add_roles(db)

if __name__ == '__main__':
    asyncio.run(main())
