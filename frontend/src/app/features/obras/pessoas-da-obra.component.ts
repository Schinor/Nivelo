import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MembroDaEquipeOut } from '../../api/models/membro-da-equipe-out';
import { ObraOut } from '../../api/models/obra-out';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { paraErroDaApi } from '../../core/http/erro-da-api';
import { data, iniciais } from '../../shared/formatos';
import { ObrasService } from './obras.service';

type PapelNaObra = 'encarregado' | 'cliente';

/**
 * Aba "Pessoas da obra" (só o dono): quem é encarregado e quem é cliente desta obra. O dono vê
 * todas as obras; encarregado e cliente só as que estão aqui. Clientes não contam no limite.
 */
@Component({
  selector: 'app-pessoas-da-obra',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink],
  template: `
    <section aria-label="Pessoas da obra" class="grade">
      @for (g of grupos(); track g.papel) {
        <div class="cartao">
          <div class="cartao-titulo">
            <h2>{{ g.titulo }}</h2>
            <span class="ajuda">{{ g.nota }}</span>
          </div>
          @for (m of g.membros; track m.usuario_id) {
            <div class="pessoa-linha">
              <span class="avatar" [class.encarregado]="g.papel === 'encarregado'">{{ iniciais(m.nome) }}</span>
              <div><strong>{{ m.nome }}</strong><span>{{ m.email }} · na equipe desde {{ data(m.desde) }}</span></div>
              <button type="button" class="btn btn-pequeno" (click)="remover(m)" [disabled]="ocupado()">Remover da obra</button>
            </div>
          } @empty {
            <p class="ajuda vazio-linha">{{ g.vazio }}</p>
          }

          @if (g.candidatos.length) {
            <form class="adicionar" (ngSubmit)="adicionar(g.papel)">
              <div class="campo">
                <label [for]="'add-' + g.papel">Adicionar alguém da equipe</label>
                <select [id]="'add-' + g.papel" [name]="'add-' + g.papel" [ngModel]="escolhido()[g.papel]"
                        (ngModelChange)="escolher(g.papel, $event)">
                  <option [ngValue]="null">Escolha…</option>
                  @for (p of g.candidatos; track p.usuario_id) { <option [ngValue]="p.usuario_id">{{ p.nome }}</option> }
                </select>
              </div>
              <button class="btn" type="submit" [disabled]="!escolhido()[g.papel] || ocupado()">Adicionar</button>
            </form>
          }
          <a class="btn btn-pequeno convidar" [class.btn-primario]="g.papel === 'cliente'" [class.btn-contorno]="g.papel !== 'cliente'"
             routerLink="/equipe" [queryParams]="{ papel: g.papel, obra: obra().id }">Convidar {{ g.papel }}</a>
        </div>
      }
    </section>
  `,
  styles: `
    .grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; align-items: start; }
    .vazio-linha { padding: 10px 0; border-top: 1px solid var(--linha-suave); }
    .adicionar { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: end; padding-top: 12px; border-top: 1px solid var(--linha-suave); }
    .convidar { align-self: flex-start; min-height: 44px; }
  `,
})
export class PessoasDaObraComponent {
  readonly obra = input.required<ObraOut>();
  readonly equipe = input.required<MembroDaEquipeOut[]>();
  readonly mudou = output<void>();

  private auth = inject(AuthService);
  private servico = inject(ObrasService);
  private avisos = inject(AvisosService);

  readonly iniciais = iniciais;
  readonly data = data;
  ocupado = signal(false);
  escolhido = signal<Record<PapelNaObra, number | null>>({ encarregado: null, cliente: null });

  readonly grupos = computed(() => {
    const membros = this.obra().membros ?? [];
    const naObra = new Set(membros.map((m) => m.usuario_id));
    const pessoa = (id: number): MembroDaEquipeOut =>
      this.equipe().find((p) => p.usuario_id === id) ?? { usuario_id: id, nome: `Pessoa nº ${id}`, email: '', papel: '', desde: '' };
    const grupo = (papel: PapelNaObra, titulo: string, nota: string, vazio: string) => ({
      papel,
      titulo,
      nota,
      vazio,
      membros: membros.filter((m) => m.papel === papel).map((m) => pessoa(m.usuario_id)),
      candidatos: this.equipe().filter((p) => p.papel === papel && !naObra.has(p.usuario_id) && p.usuario_id !== this.auth.usuarioId()),
    });
    return [
      grupo('encarregado', 'Encarregados', 'Registram os diários desta obra', 'Nenhum encarregado nesta obra. Você mesmo pode registrar os diários.'),
      grupo('cliente', 'Clientes', 'Grátis, fora do limite', 'Nenhum cliente acompanhando. Convide o cliente para ele ver os diários publicados.'),
    ];
  });

  escolher(papel: PapelNaObra, id: number | null): void {
    this.escolhido.update((e) => ({ ...e, [papel]: id }));
  }

  async adicionar(papel: PapelNaObra): Promise<void> {
    const id = this.escolhido()[papel];
    const pessoa = this.equipe().find((p) => p.usuario_id === id);
    if (!pessoa) return;
    await this.executar(async () => {
      await this.servico.adicionarMembro(this.obra().id, pessoa.usuario_id, papel);
      this.escolher(papel, null);
      this.avisos.sucesso(`${pessoa.nome} agora acompanha a obra.`);
      this.mudou.emit();
    });
  }

  async remover(m: MembroDaEquipeOut): Promise<void> {
    const ok = await this.avisos.confirmar('Remover da obra?', `${m.nome} deixa de ver esta obra, mas continua na equipe da empresa.`, {
      confirmar: 'Remover da obra',
    });
    if (!ok) return;
    await this.executar(async () => {
      await this.servico.removerMembro(this.obra().id, m.usuario_id);
      this.mudou.emit();
    });
  }

  private async executar(acao: () => Promise<void>): Promise<void> {
    this.ocupado.set(true);
    try {
      await acao();
    } catch (e) {
      const erro = paraErroDaApi(e);
      if (erro.status !== 402) this.avisos.erro(erro.mensagem);
    } finally {
      this.ocupado.set(false);
    }
  }
}
