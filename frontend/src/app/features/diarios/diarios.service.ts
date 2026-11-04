import { Injectable, inject } from '@angular/core';
import { Api } from '../../api/api';
import { comentar } from '../../api/fn/diarios/comentar';
import { confirmarFoto } from '../../api/fn/diarios/confirmar-foto';
import { detalharDiario } from '../../api/fn/diarios/detalhar-diario';
import { editarDiario } from '../../api/fn/diarios/editar-diario';
import { listarComentarios } from '../../api/fn/diarios/listar-comentarios';
import { listarDiarios } from '../../api/fn/diarios/listar-diarios';
import { pedirUploadDeFoto } from '../../api/fn/diarios/pedir-upload-de-foto';
import { publicarDiario } from '../../api/fn/diarios/publicar-diario';
import { registrarDiario } from '../../api/fn/diarios/registrar-diario';
import { removerDiario } from '../../api/fn/diarios/remover-diario';
import { removerFotoDoDiario } from '../../api/fn/diarios/remover-foto-do-diario';
import { revisoesDoDiario } from '../../api/fn/diarios/revisoes-do-diario';
import { urlDaFoto } from '../../api/fn/diarios/url-da-foto';
import { ComentarioOut } from '../../api/models/comentario-out';
import { DiarioIn } from '../../api/models/diario-in';
import { DiarioOut } from '../../api/models/diario-out';
import { FotoOut } from '../../api/models/foto-out';
import { PaginaDeComentariosOut } from '../../api/models/pagina-de-comentarios-out';
import { PaginaDeDiariosOut } from '../../api/models/pagina-de-diarios-out';
import { RevisaoOut } from '../../api/models/revisao-out';
import { comprimir } from './compressao';

/** Diários, fotos e comentários, pelo cliente gerado do OpenAPI. */
@Injectable({ providedIn: 'root' })
export class DiariosService {
  private api = inject(Api);
  private urls = new Map<string, { url: string; expira: number }>();

  listar(obraId: string, pagina = 1, porPagina = 20): Promise<PaginaDeDiariosOut> {
    return this.api.invoke(listarDiarios, { obra_id: obraId, page: pagina, por_pagina: porPagina });
  }

  detalhar(diarioId: string): Promise<DiarioOut> {
    return this.api.invoke(detalharDiario, { diario_id: diarioId });
  }

  registrar(obraId: string, diario: DiarioIn): Promise<DiarioOut> {
    return this.api.invoke(registrarDiario, { obra_id: obraId, body: diario });
  }

  /** Rascunho: edita. Publicado: vira revisão e exige `motivo`. */
  editar(diarioId: string, versao: number, diario: DiarioIn, motivo: string | null): Promise<DiarioOut> {
    return this.api.invoke(editarDiario, { diario_id: diarioId, body: { ...diario, versao, motivo } });
  }

  publicar(diarioId: string, versao: number): Promise<DiarioOut> {
    return this.api.invoke(publicarDiario, { diario_id: diarioId, body: { versao } });
  }

  remover(diarioId: string): Promise<void> {
    return this.api.invoke(removerDiario, { diario_id: diarioId });
  }

  revisoes(diarioId: string): Promise<RevisaoOut[]> {
    return this.api.invoke(revisoesDoDiario, { diario_id: diarioId });
  }

  comentarios(diarioId: string, pagina = 1): Promise<PaginaDeComentariosOut> {
    return this.api.invoke(listarComentarios, { diario_id: diarioId, page: pagina, por_pagina: 100 });
  }

  comentar(diarioId: string, texto: string): Promise<ComentarioOut> {
    return this.api.invoke(comentar, { diario_id: diarioId, body: { texto } });
  }

  /**
   * Comprime no navegador, pede a URL pré-assinada, envia o arquivo direto ao storage (PUT pela
   * ponte /storage, sem o token: a autorização é a assinatura) e confirma na API.
   */
  async enviarFoto(diarioId: string, arquivo: File, legenda: string | null): Promise<FotoOut> {
    const jpeg = await comprimir(arquivo);
    const pedido = await this.api.invoke(pedirUploadDeFoto, {
      diario_id: diarioId,
      body: { content_type: 'image/jpeg', tamanho_bytes: jpeg.size },
    });
    const envio = await fetch(pedido.url, { method: 'PUT', body: jpeg, headers: pedido.headers });
    if (!envio.ok) {
      throw new Error(envio.status === 403 ? 'O link de envio expirou. Tente de novo.' : 'Não foi possível enviar a foto.');
    }
    return this.api.invoke(confirmarFoto, { diario_id: diarioId, body: { object_key: pedido.object_key, legenda } });
  }

  removerFoto(fotoId: string): Promise<void> {
    return this.api.invoke(removerFotoDoDiario, { foto_id: fotoId });
  }

  /** URL de leitura (válida por 10 min), reaproveitada enquanto não estiver perto de expirar. */
  async urlDaFoto(fotoId: string): Promise<string> {
    const guardada = this.urls.get(fotoId);
    if (guardada && guardada.expira > Date.now()) return guardada.url;
    const r = await this.api.invoke(urlDaFoto, { foto_id: fotoId });
    this.urls.set(fotoId, { url: r.url, expira: Date.now() + (r.expira_em_segundos - 60) * 1000 });
    return r.url;
  }
}
