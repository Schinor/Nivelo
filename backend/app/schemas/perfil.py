from typing import Optional
from pydantic import BaseModel, Field, field_validator


class PerfilOut(BaseModel):
    usuario_id: int
    nome: str
    bio: Optional[str] = None
    # URL relativa ao catálogo (/storage/...), pré-assinada e com expiração; null sem foto
    foto_url: Optional[str] = None
    # Selo "Premium" (visual); os limites do plano são checados no backend
    premium: bool = False
    # Só para a UI esconder/mostrar os botões — não é controle de acesso
    pode_editar: bool = False


class PerfilBioUpdate(BaseModel):
    """Sem campo usuario_id de propósito: a identidade vem do JWT (extras são ignorados)."""

    bio: Optional[str] = Field(default=None, max_length=280)

    @field_validator("bio")
    @classmethod
    def normalizar(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None
