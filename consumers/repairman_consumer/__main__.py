import asyncio

from consumers.repairman_consumer.app import repairman_consumer


if __name__ == '__main__':
    asyncio.run(repairman_consumer())
