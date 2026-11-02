import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface PremiumStatus {
  premium: boolean;
  premium_desde: string | null;
}

@Injectable({ providedIn: 'root' })
export class PremiumService {
  constructor(private http: HttpClient) {}

  /** Plano lido do banco pelo backend — nunca da claim do JWT. */
  status(): Observable<PremiumStatus> {
    return this.http.get<PremiumStatus>('/api/premium/status');
  }

  /** Cria a sessão de checkout; o pagamento acontece só na página hospedada do Stripe. */
  checkout(): Observable<{ url: string }> {
    return this.http.post<{ url: string }>('/api/premium/checkout', {});
  }
}
