import asyncio

from consumers.start_consumer.app import start_consumer


if __name__ == '__main__':
    asyncio.run(start_consumer())
