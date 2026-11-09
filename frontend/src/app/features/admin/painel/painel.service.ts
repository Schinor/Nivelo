import { Injectable, inject } from '@angular/core';
import { Api } from '../../../api/api';
import { consultarPainel } from '../../../api/fn/admin/consultar-painel';
import { MetricasOut } from '../../../api/models/metricas-out';

/** Números da plataforma, pelo cliente gerado do OpenAPI. Só o admin; a API confere. */
@Injectable({ providedIn: 'root' })
export class PainelService {
  private api = inject(Api);

  consultar(): Promise<MetricasOut> {
    return this.api.invoke(consultarPainel, {});
  }
}
