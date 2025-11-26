from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    tenant_url: str = ""
    api_token: str = ""
    backend_port: int = 8000
    frontend_port: int = 3000

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"  # Ignore extra fields from .env
    )


settings = Settings()
