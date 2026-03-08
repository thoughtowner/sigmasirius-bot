from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    BOT_WEBHOOK_URL: str

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

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
    REVERSE_START_QUEUE_NAME: str = 'reverse_start_queue'

    RESERVATION_EXCHANGE_NAME: str = 'reservation_exchange'
    RESERVATION_QUEUE_NAME: str = 'reservation_queue'
    USER_RESERVATION_QUEUE_TEMPLATE: str = 'user_reservation_queue.{telegram_id}'

    APPLICATION_FORM_EXCHANGE_NAME: str = 'application_form_exchange'
    APPLICATION_FORM_QUEUE_NAME: str = 'application_form_queue'


    @property
    def db_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def rabbit_url(self) -> str:
        return f"amqp://{self.RABBIT_USER}:{self.RABBIT_PASSWORD}@{self.RABBIT_HOST}:{self.RABBIT_PORT}/"

    class Config:
        env_file = "config/.env"


settings = Settings()
