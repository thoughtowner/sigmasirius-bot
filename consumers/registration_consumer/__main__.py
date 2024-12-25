import asyncio

from consumers.registration_consumer.app import registration_consumer


if __name__ == '__main__':
    asyncio.run(registration_consumer())
