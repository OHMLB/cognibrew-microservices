from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=False,
        env_ignore_empty=True,
        case_sensitive=False,
    )

    API_PREFIX_STR: str = "/api/v1"
    DEBUG: bool = True  # True = skip RabbitMQ consumer

    # RabbitMQ
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USERNAME: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_INFERENCE_EXCHANGE_NAME: str = "cognibrew.inference"
    RABBITMQ_RECOMMENDATION_QUEUE_NAME: str = "cognibrew.inference.face_recognized"
    RABBITMQ_FACE_RECOGNIZED_ROUTING_KEY: str = "face.recognized"

    # Catalog Service
    CATALOG_SERVICE_URL: str = "http://catalog-service:8000"
    CATALOG_RECOMMENDATION_LIMIT: int = 5
    CATALOG_HTTP_TIMEOUT: float = 10.0

    # RabbitMQ — recommendation output (published after computing recs)
    RABBITMQ_RECOMMENDATION_EXCHANGE_NAME: str = "cognibrew.recommendation"
    RABBITMQ_MENU_RECOMMENDED_ROUTING_KEY: str = "menu.recommended"


settings = Settings()  # type: ignore
