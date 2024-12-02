import asyncio
import uuid
from contextvars import ContextVar

ctx = ContextVar('ctx')


async def print_2():
    print(ctx.get())


async def print_():
    print(ctx.get())
    await print_2()


async def with_ctx(i):

    if i == 1:
        await asyncio.sleep(1)
        print(ctx.get(None))
    ctx.set(str(uuid.uuid4()))
    await print_()


async def main():
    a = 1
    await asyncio.gather(with_ctx(1), with_ctx(2), with_ctx(3))


asyncio.run(main())
