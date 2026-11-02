from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PORT: int = 8001

    # Mailtrap / SMTP
    MAILTRAP_HOST: str = "sandbox.smtp.mailtrap.io"
    MAILTRAP_PORT: int = 2525
    MAILTRAP_USERNAME: str = ""
    MAILTRAP_PASSWORD: str = ""
    MAILTRAP_FROM_EMAIL: str = "nao-responda@nivelo.app"
    MAILTRAP_FROM_NAME: str = "Nivelo"

    # URL base pública da aplicação para geração do link no e-mail
    CATALOGO_URL: str = "http://localhost:8000"

    # Expiração do token de redefinição de senha em minutos (30 minutos)
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Limite de solicitações de redefinição por usuário dentro da janela (anti-abuso)
    RESET_REQUEST_LIMIT: int = 3
    RESET_REQUEST_WINDOW_MINUTES: int = 15

    # Somente desenvolvimento: sem credenciais SMTP, registra o link no log em vez de falhar
    EMAIL_LOG_LINK_WITHOUT_SMTP: bool = False

    # Token compartilhado com a API para as rotas /internal (webhook do Stripe já validado).
    # Vazio = rotas internas desligadas (503).
    AUTH_INTERNAL_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=(".env", "../.env", "../../.env"), extra="ignore")


settings = Settings()
