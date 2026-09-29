import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_access_token_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60"))
    app_env: str = os.getenv("APP_ENV", "production").lower()
    billing_mode: str = os.getenv("BILLING_MODE", "disabled").lower()
    jwt_issuer: str = os.getenv("JWT_ISSUER", "tender-client-api")


@lru_cache
def get_settings() -> Settings:
    return Settings()
