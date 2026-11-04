import { Injectable, inject } from '@angular/core';
import { Api } from '../../api/api';
import { adicionarMembro } from '../../api/fn/obras/adicionar-membro';
import { alterarStatus } from '../../api/fn/obras/alterar-status';
import { criarObra } from '../../api/fn/obras/criar-obra';
import { detalharObra } from '../../api/fn/obras/detalhar-obra';
import { editarObra } from '../../api/fn/obras/editar-obra';
import { historicoDaObra } from '../../api/fn/obras/historico-da-obra';
import { listarObras } from '../../api/fn/obras/listar-obras';
import { removerMembro } from '../../api/fn/obras/remover-membro';
import { removerObra } from '../../api/fn/obras/remover-obra';
import { EventoDoHistoricoOut } from '../../api/models/evento-do-historico-out';
import { MembroOut } from '../../api/models/membro-out';
import { ObraIn } from '../../api/models/obra-in';
import { ObraOut } from '../../api/models/obra-out';
import { PaginaDeObrasOut } from '../../api/models/pagina-de-obras-out';

export type StatusObra = 'ativa' | 'pausada' | 'concluida';

/** Obras e membros, pelo cliente gerado do OpenAPI. A empresa vem do token, nunca daqui. */
@Injectable({ providedIn: 'root' })
export class ObrasService {
  private api = inject(Api);

  listar(status: StatusObra | null, pagina = 1, porPagina = 20): Promise<PaginaDeObrasOut> {
    return this.api.invoke(listarObras, { status, page: pagina, por_pagina: porPagina });
  }

  detalhar(obraId: string): Promise<ObraOut> {
    return this.api.invoke(detalharObra, { obra_id: obraId });
  }

  criar(obra: ObraIn): Promise<ObraOut> {
    return this.api.invoke(criarObra, { body: obra });
  }

  editar(obraId: string, versao: number, obra: ObraIn): Promise<ObraOut> {
    return this.api.invoke(editarObra, { obra_id: obraId, body: { ...obra, versao } });
  }

  alterarStatus(obraId: string, status: StatusObra, versao: number): Promise<ObraOut> {
    return this.api.invoke(alterarStatus, { obra_id: obraId, body: { status, versao } });
  }

  remover(obraId: string): Promise<void> {
    return this.api.invoke(removerObra, { obra_id: obraId });
  }

  adicionarMembro(obraId: string, usuarioId: number, papel: 'encarregado' | 'cliente'): Promise<MembroOut> {
    return this.api.invoke(adicionarMembro, { obra_id: obraId, body: { usuario_id: usuarioId, papel } });
  }

  removerMembro(obraId: string, usuarioId: number): Promise<void> {
    return this.api.invoke(removerMembro, { obra_id: obraId, usuario_id: usuarioId });
  }

  historico(obraId: string, limite = 50): Promise<EventoDoHistoricoOut[]> {
    return this.api.invoke(historicoDaObra, { obra_id: obraId, limite });
  }
}
