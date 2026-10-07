from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', hide_input_in_errors=True)
    database_url: str
    jwt_secret: str = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
    frontend_origin: str = 'http://localhost:5173'
    openai_api_key: SecretStr = SecretStr('')
    openai_model: str = 'gpt-4.1-mini'
    llm_timeout_seconds: float = Field(default=15, ge=1, le=60)
    auth_rate_limit: int = Field(default=30,ge=1,le=1000)
    api_rate_limit: int = Field(default=600,ge=1,le=10000)
    analysis_rate_limit: int = Field(default=60,ge=1,le=1000)


settings = Settings()
