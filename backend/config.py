from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tenant_url: str = ""
    api_token: str = ""
    backend_port: int = 8000
    frontend_port: int = 3000

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env


settings = Settings()
