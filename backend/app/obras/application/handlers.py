"""Casos de uso de escrita de Gestão de Obras: um handler por comando.

O papel de quem chama já foi conferido na borda (`requer_papel`, com o 403 auditado). Aqui
ficam as regras que dependem do estado: tenant (o repositório só enxerga a empresa do
contexto), versão (409), plano (402) e as invariantes do agregado.
"""

from __future__ import annotations

from app.assinaturas.domain.planos import PoliticaDePlano
from app.obras.application.comandos import (
    AdicionarMembro,
    AlterarStatusObra,
    CriarObra,
    DadosDaObra,
    EditarObra,
    RemoverMembro,
    RemoverObra,
)
from app.obras.application.portas import EquipeDaEmpresa, UnidadeDeTrabalhoDeObras
from app.obras.domain.erros import MembroInvalido, TransicaoDeStatusInvalida
from app.obras.domain.obra import Obra
from app.obras.domain.valores import Endereco, PapelDeMembro, Periodo, StatusObra
from app.shared.application.contexto import TenantContext
from app.shared.domain.erros import ConflitoDeVersao
from app.shared.domain.ids import UsuarioId
from app.shared.domain.relogio import Relogio


def _endereco(d: DadosDaObra) -> Endereco:
    return Endereco(logradouro=d.logradouro, cidade=d.cidade, uf=d.uf, latitude=d.latitude, longitude=d.longitude)


def _ator(ctx: TenantContext) -> UsuarioId:
    return UsuarioId(ctx.usuario_id)


def _conferir_versao(obra: Obra, esperada: int | None) -> None:
    if esperada is not None and esperada != obra.versao:
        raise ConflitoDeVersao(versao_atual=obra.versao)


def _exigir_vaga_de_obra_ativa(uow: UnidadeDeTrabalhoDeObras, ctx: TenantContext) -> None:
    # Trava a assinatura antes de contar: duas requisições ao mesmo tempo esperam uma pela outra
    efetivos = uow.direitos.travar_e_obter(ctx.empresa_id)
    PoliticaDePlano.exigir_vaga_de_obra_ativa(efetivos, uow.obras.contar_ativas())


def criar_obra(cmd: CriarObra, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras) -> Obra:
    d = cmd.dados
    with uow:
        obra = Obra.criar(
            empresa_id=ctx.empresa_id,
            nome=d.nome,
            endereco=_endereco(d),
            cliente_nome=d.cliente_nome,
            periodo=Periodo(d.data_inicio, d.previsao_termino),
            ator=_ator(ctx),
        )
        _exigir_vaga_de_obra_ativa(uow, ctx)
        uow.obras.adicionar(obra)
        uow.commit()
    return obra


def editar_obra(cmd: EditarObra, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras) -> Obra:
    d = cmd.dados
    with uow:
        obra = uow.obras.obter(cmd.obra_id)
        _conferir_versao(obra, cmd.versao_esperada)
        obra.editar(
            nome=d.nome,
            endereco=_endereco(d),
            cliente_nome=d.cliente_nome,
            periodo=Periodo(d.data_inicio, d.previsao_termino),
            ator=_ator(ctx),
        )
        uow.obras.salvar(obra)
        uow.commit()
    return obra


def alterar_status_obra(cmd: AlterarStatusObra, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras) -> Obra:
    try:
        novo = StatusObra(cmd.status)
    except ValueError:
        raise TransicaoDeStatusInvalida("Status deve ser ativa, pausada ou concluida.") from None
    with uow:
        obra = uow.obras.obter(cmd.obra_id)
        _conferir_versao(obra, cmd.versao_esperada)
        obra.alterar_status(novo, _ator(ctx))
        if novo is StatusObra.ATIVA:
            # Reativar ocupa uma vaga de obra ativa (a própria obra ainda não conta: está pausada)
            _exigir_vaga_de_obra_ativa(uow, ctx)
        uow.obras.salvar(obra)
        uow.commit()
    return obra


def remover_obra(cmd: RemoverObra, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, relogio: Relogio) -> None:
    with uow:
        obra = uow.obras.obter(cmd.obra_id)
        _conferir_versao(obra, cmd.versao_esperada)
        obra.remover(_ator(ctx), relogio.agora())
        uow.obras.salvar(obra)
        uow.commit()


def adicionar_membro(
    cmd: AdicionarMembro, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, equipe: EquipeDaEmpresa
) -> Obra:
    papel = PapelDeMembro.de_texto(cmd.papel)
    with uow:
        obra = uow.obras.obter(cmd.obra_id)  # 404 antes de consultar a equipe
        papel_na_empresa = equipe.papel_de(cmd.usuario_id)
        if papel_na_empresa is None:
            raise MembroInvalido("Essa pessoa não faz parte da empresa. Convide-a por e-mail primeiro.")
        if papel_na_empresa != papel.value:
            raise MembroInvalido(
                f"Essa pessoa está na empresa como {papel_na_empresa} e não pode entrar na obra como {papel.value}."
            )
        obra.adicionar_membro(cmd.usuario_id, papel, _ator(ctx))
        uow.obras.salvar(obra)
        uow.commit()
    return obra


def remover_membro(cmd: RemoverMembro, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras) -> None:
    with uow:
        obra = uow.obras.obter(cmd.obra_id)
        obra.remover_membro(cmd.usuario_id, _ator(ctx))
        uow.obras.salvar(obra)
        uow.commit()
