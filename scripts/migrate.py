import asyncio

from src.model.meta import metadata
from src.storage.db import engine


async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.commit()


if __name__ == '__main__':
    asyncio.run(migrate())
