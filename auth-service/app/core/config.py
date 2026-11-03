from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # 2 h, sem refresh token até 13/11 (docs/adr/005)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    PORT: int = 8001

    # Mailtrap / SMTP
    MAILTRAP_HOST: str = "sandbox.smtp.mailtrap.io"
    MAILTRAP_PORT: int = 2525
    MAILTRAP_USERNAME: str = ""
    MAILTRAP_PASSWORD: str = ""
    MAILTRAP_FROM_EMAIL: str = "nao-responda@nivelo.app"
    MAILTRAP_FROM_NAME: str = "Nivelo"

    # URL base pública da aplicação para os links dos e-mails. APP_BASE_URL é o nome novo;
    # CATALOGO_URL continua aceito enquanto a stack antiga existir.
    APP_BASE_URL: str = ""
    CATALOGO_URL: str = "http://localhost:8000"

    # Convite para entrar numa empresa: validade e uso único (o banco guarda só o hash)
    CONVITE_VALIDADE_HORAS: int = 72

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

    # Admin da plataforma criado no primeiro boot, nunca pelo cadastro público.
    # Se o e-mail já existir, só garante a marca de admin (a senha não é trocada).
    ADMIN_EMAIL: str = ""
    ADMIN_SENHA_INICIAL: str = ""

    model_config = SettingsConfigDict(env_file=(".env", "../.env", "../../.env"), extra="ignore")


settings = Settings()
