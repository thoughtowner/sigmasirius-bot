from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    BOT_WEBHOOK_URL: str

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    RABBIT_HOST: str = 'localhost' # rabbitmq
    RABBIT_PORT: int = 5672
    RABBIT_USER: str = 'guest'
    RABBIT_PASSWORD: str = 'guest'

    REDIS_HOST: str
    REDIS_PORT: int

    MINIO_USER: str
    MINIO_PASSWORD: str
    MINIO_HOST: str

    START_EXCHANGE_NAME: str = 'start_exchange'
    START_QUEUE_NAME: str = 'start_queue'

    REGISTRATION_EXCHANGE_NAME: str = 'registration_exchange'
    REGISTRATION_QUEUE_NAME: str = 'registration_queue'
    USER_REGISTRATION_QUEUE_TEMPLATE: str = 'user_registration_queue.{telegram_user_id}'

    ADD_APPLICATION_FORM_EXCHANGE_NAME: str = 'add_application_form_exchange'
    ADD_APPLICATION_FORM_QUEUE_NAME: str = 'add_application_form_queue'
    USER_ADD_APPLICATION_FORM_QUEUE_NAME: str = 'user_add_application_form_queue'


    @property
    def db_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def rabbit_url(self) -> str:
        return f"amqp://{self.RABBIT_USER}:{self.RABBIT_PASSWORD}@{self.RABBIT_HOST}:{self.RABBIT_PORT}/"

    class Config:
        env_file = "config/.env"


settings = Settings()
