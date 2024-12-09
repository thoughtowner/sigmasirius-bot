from uuid import uuid4

from asyncpg import Connection
from sqlalchemy import AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from typing_extensions import AsyncGenerator

from config.settings import settings

from sqlalchemy.future import select
from sqlalchemy import insert
import asyncio

from consumers.model.models import User, Role, ResidentAdditionalData, UserRole


class CConnection(Connection):
    def _get_unique_id(self, prefix: str) -> str:
        return f'__asyncpg_{prefix}_{uuid4()}__'


def create_engine() -> AsyncEngine:
    return create_async_engine(
        settings.db_url,
        poolclass=AsyncAdaptedQueuePool,
        connect_args={
            'connection_class': CConnection,
            # 'pool_recycle': 3600,
            # 'pool_size': 5,
            # 'pool_overflow': 10,
        },
    )


def create_session(_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


engine = create_engine()
async_session = create_session(engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as db:
        yield db


async def add_data(db: AsyncSession):
    user_instance = User(
        telegram_user_id=123456789,
        full_name='full_name',
        phone_number='phone_number'
    )

    resident_additional_data_instance = ResidentAdditionalData(
        room='room'
    )

    role_instance = Role(
        title='resident'
    )

    role_result = await db.execute(select(Role.id).filter(Role.title == role_instance.title))
    role_id = role_result.scalar()

    user_query = insert(User).values(
        telegram_user_id=user_instance.telegram_user_id,
        full_name=user_instance.full_name,
        phone_number=user_instance.phone_number,
    ).returning(User.id)

    user_result = await db.execute(user_query)
    user_id = user_result.scalar()

    resident_additional_data_query = insert(ResidentAdditionalData).values(
        room=resident_additional_data_instance.room,
        user_id=user_id
    )

    await db.execute(resident_additional_data_query)

    user_role_query = insert(UserRole).values(
        user_id=user_id,
        role_id=role_id,
    )

    await db.execute(user_role_query)

    await db.commit()

async def create_data():
    async with async_session() as db:
        await add_data(db)

if __name__ == '__main__':
    asyncio.run(create_data())


# async def add_roles(db: AsyncSession):
#     new_roles = [
#         Role(title='resident'),
#         Role(title='admin')
#     ]
#     db.add_all(new_roles)
#     await db.commit()
#
#     result = await db.execute(select(Role).filter(Role.title.in_(['resident', 'admin'])))
#     roles = result.scalars().all()
#     print("Added roles:", roles)
#
#
# async def create_roles():
#     async with async_session() as db:
#         await add_roles(db)
#
#
# if __name__ == '__main__':
#     asyncio.run(create_roles())
