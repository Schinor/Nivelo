import { Injectable, inject } from '@angular/core';
import { Api } from '../../api/api';
import { consultarAssinatura } from '../../api/fn/assinaturas/consultar-assinatura';
import { criarCheckout } from '../../api/fn/assinaturas/criar-checkout';
import { criarPortal } from '../../api/fn/assinaturas/criar-portal';
import { AssinaturaOut } from '../../api/models/assinatura-out';

export type PlanoPago = 'pro' | 'construtora';

/** Plano e uso da empresa ativa, pelo cliente gerado do OpenAPI. A empresa vem do token. */
@Injectable({ providedIn: 'root' })
export class AssinaturaService {
  private api = inject(Api);

  consultar(): Promise<AssinaturaOut> {
    return this.api.invoke(consultarAssinatura, {});
  }

  /** URL do checkout hospedado pelo Stripe. */
  async urlDoCheckout(plano: PlanoPago): Promise<string> {
    return (await this.api.invoke(criarCheckout, { body: { plano } })).url;
  }

  /** URL do portal, onde o dono troca de plano, atualiza o cartão ou cancela. */
  async urlDoPortal(): Promise<string> {
    return (await this.api.invoke(criarPortal, {})).url;
  }
}
