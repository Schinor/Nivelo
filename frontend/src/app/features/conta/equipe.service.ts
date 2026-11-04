import { Injectable, inject } from '@angular/core';
import { Api } from '../../api/api';
import { listarEquipe } from '../../api/fn/auth/listar-equipe';
import { aceitar } from '../../api/fn/convites/aceitar';
import { convidar } from '../../api/fn/convites/convidar';
import { AceiteOut } from '../../api/models/aceite-out';
import { ConviteOut } from '../../api/models/convite-out';
import { MembroDaEquipeOut } from '../../api/models/membro-da-equipe-out';

/** Equipe da empresa ativa e convites (só o dono convida e vê a equipe; a API confere). */
@Injectable({ providedIn: 'root' })
export class EquipeService {
  private api = inject(Api);

  equipe(): Promise<MembroDaEquipeOut[]> {
    return this.api.invoke(listarEquipe, {});
  }

  convidar(email: string, papel: 'encarregado' | 'cliente', obraId: string | null): Promise<ConviteOut> {
    return this.api.invoke(convidar, { body: { email, papel, obra_id: obraId } });
  }

  aceitar(token: string, nome: string | null, senha: string | null): Promise<AceiteOut> {
    return this.api.invoke(aceitar, { body: { token, nome, senha } });
  }
}
