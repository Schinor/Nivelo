from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PORT: int = 8000
    AUTH_SERVICE_URL: str = "http://auth-service:8001"
    LOG_SERVICE_URL: str = "http://log-service:8002"
    LOG_INTERNAL_TOKEN: str = ""
    GRAFANA_INTERNAL_URL: str = "http://grafana:3000"
    PROMETHEUS_INTERNAL_URL: str = "http://prometheus:9090"
    PROMETHEUS_PROXY_PASSWORD: str = ""
    # Object storage (Garage, API S3) — foto de perfil
    STORAGE_ENDPOINT: str = "http://garage:3900"
    STORAGE_REGION: str = "garage"
    STORAGE_BUCKET: str = "catalogo-avatares"
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    STORAGE_BANDA_MINIMA_KBPS: int = 256
    STORAGE_MARGEM_USO_SEGUNDOS: int = 600
    STORAGE_EXPIRACAO_MAX_SEGUNDOS: int = 3600
    PERFIL_FOTO_MAX_BYTES: int = 2 * 1024 * 1024
    # Plano Premium (Stripe, SEMPRE em modo de teste). Sem as chaves, checkout e webhook respondem 503
    # e o resto do catálogo segue funcionando (CI e deploys antigos não têm Stripe).
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""
    # Para onde o Stripe devolve o usuário depois do checkout (a SPA é servida pelo próprio catálogo)
    FRONTEND_URL: str = "http://localhost:8000"
    # Token compartilhado com o auth-service para as rotas /internal (gravar o status premium)
    AUTH_INTERNAL_TOKEN: str = ""

    @field_validator("STRIPE_SECRET_KEY")
    @classmethod
    def somente_modo_teste(cls, valor: str) -> str:
        # Falha cedo: chave live cobraria cartões de verdade
        if valor.startswith(("sk_live_", "rk_live_")):
            raise ValueError("STRIPE_SECRET_KEY é uma chave LIVE; esta aplicação só aceita chaves de teste (sk_test_...)")
        return valor

    @property
    def stripe_configurado(self) -> bool:
        return bool(self.STRIPE_SECRET_KEY and self.STRIPE_WEBHOOK_SECRET and self.STRIPE_PRICE_ID)

    model_config = SettingsConfigDict(env_file=(".env", "../.env", "../../.env"), extra="ignore")


settings = Settings()
