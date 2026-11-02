from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Perfil(Base):
    """Dados de perfil do usuário na API (a conta em si fica no auth-service).

    A linha é criada sob demanda na primeira edição; sem linha = bio vazia e sem foto.
    Sem FK para `usuarios`: a tabela pertence ao auth-service (um contexto não lê as
    tabelas de outro); a limpeza na remoção do usuário é feita pela rota de exclusão.
    """

    __tablename__ = "perfis"

    usuario_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    bio: Mapped[str | None] = mapped_column(String(280), nullable=True)
    # Só a CHAVE do objeto no bucket, nunca a URL (a URL assinada é gerada a cada leitura)
    foto_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Tamanho em bytes, usado no cálculo da expiração da URL assinada
    foto_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=func.now(),
    )
