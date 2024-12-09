from sqlalchemy.future import select
from sqlalchemy import insert

from consumers.model.models import User, Role, UserRole

from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.db import async_session


async def add_admins(db: AsyncSession):
    admin_role_result = await db.execute(select(Role.id).filter(Role.title == 'admin'))
    admin_role_id = admin_role_result.scalar()

    admin1_query = insert(User).values(
        telegram_user_id=1,
        full_name='Admin Aaa Aaa',
        phone_number='+7 (999) 999-99-99'
    ).returning(User.id)

    admin2_query = insert(User).values(
        telegram_user_id=2,
        full_name='Admin Bbb Ccc',
        phone_number='+7 (999) 999-99-99'
    ).returning(User.id)

    admin3_query = insert(User).values(
        telegram_user_id=3,
        full_name='Admin Ccc Ccc',
        phone_number='+7 (999) 999-99-99'
    ).returning(User.id)

    admin1_result = await db.execute(admin1_query)
    admin1_id = admin1_result.scalar()

    admin2_result = await db.execute(admin2_query)
    admin2_id = admin2_result.scalar()

    admin3_result = await db.execute(admin3_query)
    admin3_id = admin3_result.scalar()

    user_role_admin1_query = insert(UserRole).values(
        user_id=admin1_id,
        role_id=admin_role_id,
    )

    user_role_admin2_query = insert(UserRole).values(
        user_id=admin2_id,
        role_id=admin_role_id,
    )

    user_role_admin3_query = insert(UserRole).values(
        user_id=admin3_id,
        role_id=admin_role_id,
    )

    await db.execute(user_role_admin1_query)
    await db.execute(user_role_admin2_query)
    await db.execute(user_role_admin3_query)
    await db.commit()

async def main():
    async with async_session() as db:
        await add_admins(db)
