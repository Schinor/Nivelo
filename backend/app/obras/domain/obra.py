"""Agregado Obra: a raiz guarda os dados da obra, o status e os membros (Parte A.3).

Invariantes:
- a previsão de término não é antes do início (`Periodo`);
- status: ativa ↔ pausada, ativa|pausada → concluida; concluida é final;
- membro só com papel encarregado ou cliente, sem repetir o mesmo usuário;
- obra removida (soft delete) não muda mais.

Os eventos ficam em memória até a unidade de trabalho recolhê-los (`puxar_eventos`).
"""

from __future__ import annotations

from datetime import datetime

from app.obras.domain.erros import (
    MembroDuplicado,
    MembroNaoEncontrado,
    ObraNaoEncontrada,
    TransicaoDeStatusInvalida,
)
from app.obras.domain.eventos import (
    EventoDaObra,
    MembroAdicionado,
    MembroRemovido,
    ObraCriada,
    ObraEditada,
    ObraRemovida,
    ObraStatusAlterado,
)
from app.obras.domain.ids import ObraId
from app.obras.domain.valores import (
    Endereco,
    MembroDaObra,
    PapelDeMembro,
    Periodo,
    StatusObra,
    texto_obrigatorio,
)
from app.shared.domain.ids import EmpresaId, UsuarioId

ROTULO_DO_STATUS = {StatusObra.ATIVA: "ativa", StatusObra.PAUSADA: "pausada", StatusObra.CONCLUIDA: "concluída"}


class Obra:
    def __init__(
        self,
        *,
        id: ObraId,
        empresa_id: EmpresaId,
        nome: str,
        endereco: Endereco,
        cliente_nome: str,
        periodo: Periodo,
        status: StatusObra,
        criado_por: UsuarioId,
        membros: list[MembroDaObra] | None = None,
        versao: int = 1,
        removida_em: datetime | None = None,
    ) -> None:
        """Reconstitui uma obra que já existe (o repositório usa). Obra nova: `Obra.criar`."""
        self.id = id
        self.empresa_id = empresa_id
        self.nome = texto_obrigatorio(nome, "o nome da obra", 160)
        self.endereco = endereco
        self.cliente_nome = texto_obrigatorio(cliente_nome, "o nome do cliente", 160)
        self.periodo = periodo
        self.status = status
        self.criado_por = criado_por
        self.versao = versao
        self.removida_em = removida_em
        self._membros: dict[UsuarioId, MembroDaObra] = {m.usuario_id: m for m in membros or []}
        self._eventos: list[EventoDaObra] = []

    # ── Fábrica ───────────────────────────────────────────────────────────────

    @classmethod
    def criar(
        cls,
        *,
        empresa_id: EmpresaId,
        nome: str,
        endereco: Endereco,
        cliente_nome: str,
        periodo: Periodo,
        ator: UsuarioId,
        id: ObraId | None = None,
    ) -> Obra:
        obra = cls(
            id=id or ObraId.novo(),
            empresa_id=empresa_id,
            nome=nome,
            endereco=endereco,
            cliente_nome=cliente_nome,
            periodo=periodo,
            status=StatusObra.ATIVA,
            criado_por=ator,
        )
        obra._registrar(ObraCriada(empresa_id=empresa_id, ator_id=ator, obra_id=obra.id, nome=obra.nome))
        return obra

    # ── Comportamento ─────────────────────────────────────────────────────────

    @property
    def ativa(self) -> bool:
        return self.status is StatusObra.ATIVA and self.removida_em is None

    @property
    def membros(self) -> tuple[MembroDaObra, ...]:
        return tuple(self._membros.values())

    def editar(self, *, nome: str, endereco: Endereco, cliente_nome: str, periodo: Periodo, ator: UsuarioId) -> None:
        self._exigir_existente()
        novos = {
            "nome": texto_obrigatorio(nome, "o nome da obra", 160),
            "endereco": endereco,
            "cliente_nome": texto_obrigatorio(cliente_nome, "o nome do cliente", 160),
            "periodo": periodo,
        }
        campos = tuple(campo for campo, valor in novos.items() if getattr(self, campo) != valor)
        if not campos:
            return
        self.nome = str(novos["nome"])
        self.endereco = endereco
        self.cliente_nome = str(novos["cliente_nome"])
        self.periodo = periodo
        self._registrar(ObraEditada(empresa_id=self.empresa_id, ator_id=ator, obra_id=self.id, campos=campos))

    def alterar_status(self, novo: StatusObra, ator: UsuarioId) -> None:
        self._exigir_existente()
        if novo is self.status:
            raise TransicaoDeStatusInvalida(f"A obra já está {ROTULO_DO_STATUS[novo]}.")
        if not self.status.pode_ir_para(novo):
            raise TransicaoDeStatusInvalida(
                f"Uma obra {ROTULO_DO_STATUS[self.status]} não pode ficar {ROTULO_DO_STATUS[novo]}."
                + (" Obra concluída não muda mais de status." if self.status is StatusObra.CONCLUIDA else "")
            )
        anterior = self.status
        self.status = novo
        self._registrar(
            ObraStatusAlterado(
                empresa_id=self.empresa_id, ator_id=ator, obra_id=self.id, de=anterior.value, para=novo.value
            )
        )

    def remover(self, ator: UsuarioId, quando: datetime) -> None:
        """Soft delete: some das listagens e do limite do plano, e o histórico fica no banco."""
        self._exigir_existente()
        self.removida_em = quando
        self._registrar(ObraRemovida(empresa_id=self.empresa_id, ator_id=ator, obra_id=self.id))

    def adicionar_membro(self, usuario_id: UsuarioId, papel: PapelDeMembro, ator: UsuarioId) -> MembroDaObra:
        self._exigir_existente()
        if usuario_id in self._membros:
            raise MembroDuplicado("Essa pessoa já é membro da obra.")
        membro = MembroDaObra(usuario_id=usuario_id, papel=papel)
        self._membros[usuario_id] = membro
        self._registrar(
            MembroAdicionado(
                empresa_id=self.empresa_id, ator_id=ator, obra_id=self.id, usuario_id=usuario_id, papel=papel.value
            )
        )
        return membro

    def remover_membro(self, usuario_id: UsuarioId, ator: UsuarioId) -> None:
        self._exigir_existente()
        if self._membros.pop(usuario_id, None) is None:
            raise MembroNaoEncontrado()
        self._registrar(
            MembroRemovido(empresa_id=self.empresa_id, ator_id=ator, obra_id=self.id, usuario_id=usuario_id)
        )

    def visivel_para(self, usuario_id: UsuarioId, papel: str) -> bool:
        """Dono vê todas as obras da empresa; encarregado e cliente, só aquelas em que são
        membros com o próprio papel. Obra removida não é vista por ninguém."""
        if self.removida_em is not None:
            return False
        if papel == "dono":
            return True
        membro = self._membros.get(usuario_id)
        return membro is not None and membro.papel.value == papel

    # ── Eventos ───────────────────────────────────────────────────────────────

    def puxar_eventos(self) -> list[EventoDaObra]:
        eventos, self._eventos = self._eventos, []
        return eventos

    def _registrar(self, evento: EventoDaObra) -> None:
        self._eventos.append(evento)

    def _exigir_existente(self) -> None:
        if self.removida_em is not None:
            raise ObraNaoEncontrada()
