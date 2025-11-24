import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tenant_url: str = os.getenv("TENANT_URL", "")
    api_token: str = os.getenv("API_TOKEN", "")
    backend_port: int = int(os.getenv("BACKEND_PORT", 8000))
    frontend_port: int = int(os.getenv("FRONTEND_PORT", 3000))

    class Config:
        env_file = ".env"


settings = Settings()
