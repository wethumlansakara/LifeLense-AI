from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str
    jwt_secret: str = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
    frontend_origin: str = 'http://localhost:5173'


settings = Settings()
