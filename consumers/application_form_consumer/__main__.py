import asyncio

from consumers.application_form_consumer.app import application_form_consumer


if __name__ == '__main__':
    asyncio.run(application_form_consumer())
