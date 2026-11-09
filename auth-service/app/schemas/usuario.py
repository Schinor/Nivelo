from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    admin: bool = False
    criado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
