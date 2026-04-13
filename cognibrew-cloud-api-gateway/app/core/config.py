import os
from typing import Literal
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=False,
        env_ignore_empty=True,
        case_sensitive=False,
    )

    API_PREFIX_STR: str = "/api/v1"
    PROJECT_NAME: str = "CogniBrew Cloud API Gateway"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    DEBUG: bool = True

    # HTTP client timeout (seconds)
    HTTP_TIMEOUT: float = 30.0

    # RabbitMQ (for recognition consumer)
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USERNAME: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"

    # JWT — must match User Management Service settings
    JWT_SECRET_KEY: str = "DEFAULT-SECRET-KEY"
    JWT_ISSUER: str = "DEFAULT-ISSUER"
    JWT_AUDIENCE: str = "DEFAULT-AUDIENCE"
    JWT_ALGORITHMS: str = "HS256"

    @computed_field  # ← Pydantic v2
    @property
    def CATALOG_SERVICE_URL(self) -> str:
        if override := os.getenv("CATALOG_SERVICE_URL"):
            return override
        if self.ENVIRONMENT == "local" or self.DEBUG:
            return "http://localhost:8000"
        return "http://catalog-service:8000"

    @computed_field
    @property
    def RECOMMENDATION_SERVICE_URL(self) -> str:
        if override := os.getenv("RECOMMENDATION_SERVICE_URL"):
            return override
        if self.ENVIRONMENT == "local" or self.DEBUG:
            return "http://localhost:8002"
        return "http://recommendation-service:8000"

    @computed_field
    @property
    def USER_MANAGEMENT_SERVICE_URL(self) -> str:
        if override := os.getenv("USER_MANAGEMENT_SERVICE_URL"):
            return override
        if self.ENVIRONMENT == "local" or self.DEBUG:
            return "http://localhost:8003"
        return "http://user-management-service:5001"

    @computed_field
    @property
    def FEEDBACK_SERVICE_URL(self) -> str:
        if override := os.getenv("FEEDBACK_SERVICE_URL"):
            return override
        if self.ENVIRONMENT == "local" or self.DEBUG:
            return "http://localhost:5086"
        return "http://feedback-service:8080"

    @computed_field
    @property
    def NOTIFICATION_SERVICE_URL(self) -> str:
        if override := os.getenv("NOTIFICATION_SERVICE_URL"):
            return override
        if self.ENVIRONMENT == "local" or self.DEBUG:
            return "http://localhost:5019"
        return "http://notification-service:8080"


settings = Settings()  # type: ignore
