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
    PROJECT_NAME: str = "CogniBrew Catalog Service"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    
    # Max recommendations to return by default
    DEFAULT_RECOMMENDATION_LIMIT: int = 5

    @computed_field
    @property
    def MENU_SEED_FILE(self) -> str:
        """เลือก seed file ตาม environment: ใช้ test data ใน local, ใช้จริงใน staging/production."""
        if self.ENVIRONMENT == "local":
            return "data_test/menu_seed_test.json"  # ← test data
        return "data/menu_seed.json"  # ← จริง


settings = Settings()  # type: ignore