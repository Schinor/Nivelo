from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379/0"
    LOG_INTERNAL_TOKEN: str
    PORT: int = 8002

    @field_validator("LOG_INTERNAL_TOKEN")
    @classmethod
    def token_obrigatorio(cls, valor: str) -> str:
        # Token vazio aceitaria qualquer chamada com o cabeçalho vazio: o serviço não sobe
        if not valor.strip():
            raise ValueError("LOG_INTERNAL_TOKEN vazio: defina o token compartilhado com a API")
        return valor

    model_config = SettingsConfigDict(env_file=(".env", "../.env", "../../.env"), extra="ignore")


settings = Settings()
