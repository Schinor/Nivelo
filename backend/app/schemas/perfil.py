from pydantic import BaseModel, Field, field_validator


class PerfilOut(BaseModel):
    usuario_id: int
    nome: str
    bio: str | None = None
    # URL relativa à API (/storage/...), pré-assinada e com expiração; null sem foto
    foto_url: str | None = None
    # Só para a UI esconder/mostrar os botões — não é controle de acesso
    pode_editar: bool = False


class PerfilBioUpdate(BaseModel):
    """Sem campo usuario_id de propósito: a identidade vem do JWT (extras são ignorados)."""

    bio: str | None = Field(default=None, max_length=280)

    @field_validator("bio")
    @classmethod
    def normalizar(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None
