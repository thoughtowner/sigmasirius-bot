from sqlalchemy.future import select

from consumers.model.models import Role

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session


async def add_roles(db: AsyncSession):
    new_roles = [
        Role(title='resident'),
        Role(title='admin')
    ]
    db.add_all(new_roles)
    await db.commit()

    result = await db.execute(select(Role).filter(Role.title.in_(['resident', 'admin'])))
    roles = result.scalars().all()
    print("Added roles:", roles)


async def main():
    async with async_session() as db:
        await add_roles(db)
