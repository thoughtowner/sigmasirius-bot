import asyncio

from consumers.reservation_consumer.app import reservation_consumer


if __name__ == '__main__':
    asyncio.run(reservation_consumer())
