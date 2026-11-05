import { Component, OnInit, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MembroDaEquipeOut } from '../../api/models/membro-da-equipe-out';
import { ObraResumoOut } from '../../api/models/obra-resumo-out';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, mensagemDe, paraErroDaApi } from '../../core/http/erro-da-api';
import { data, PAPEL } from '../../shared/formatos';
import { ObrasService } from '../obras/obras.service';
import { EquipeService } from './equipe.service';

/** Equipe da empresa ativa e convites por e-mail. Só o dono (guard e API). */
@Component({
  selector: 'app-equipe',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="pagina">
      <header class="cabecalho">
        <div>
          <h1>Equipe</h1>
          <p class="sub">Quem trabalha nas obras da {{ auth.contexto()?.empresa_nome }} e quem as acompanha.</p>
        </div>
      </header>

      <section aria-labelledby="conv-t" class="cartao cartao-g">
        <h2 id="conv-t">Convidar pessoa</h2>
        <form class="convite" (ngSubmit)="convidar()" #f="ngForm">
          <div class="campo email" [class.invalido]="erro()?.campo('email')">
            <label for="email">E-mail</label>
            <input id="email" name="email" type="email" inputmode="email" autocomplete="off" placeholder="pessoa@email.com" [(ngModel)]="email" required />
            @if (erro()?.campo('email')) { <span class="erro-campo">E-mail inválido.</span> }
          </div>
          <div class="campo">
            <label for="papel">Papel</label>
            <select id="papel" name="papel" [(ngModel)]="papel">
              <option value="encarregado">Encarregado</option>
              <option value="cliente">Cliente</option>
            </select>
          </div>
          <div class="campo">
            <label for="obra">Obra</label>
            <select id="obra" name="obra" [(ngModel)]="obraId">
              <option [ngValue]="null">Nenhuma por enquanto</option>
              @for (o of obras(); track o.id) { <option [ngValue]="o.id">{{ o.nome }}</option> }
            </select>
          </div>
          <button type="submit" class="btn btn-primario" [disabled]="enviando() || f.invalid">{{ enviando() ? 'Enviando…' : 'Enviar convite' }}</button>
        </form>
        @if (erro(); as e) { <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p> }
        <div class="papeis">
          <div><strong>Dono</strong><span>Gerencia obras, equipe e assinatura.</span></div>
          <div><strong>Encarregado</strong><span>Registra os diários das obras em que está.</span></div>
          <div><strong>Cliente</strong><span>Acompanha e comenta. Grátis e fora do limite.</span></div>
        </div>
        <p class="alerta alerta-aviso">
          O convite vale por 72 horas. Com obra escolhida, a pessoa já entra nela ao aceitar. No plano Free, a equipe é o dono e
          1 encarregado; <a routerLink="/assinatura">assine o Pro</a> para ter até 5 pessoas. Clientes não contam no limite.
        </p>
      </section>

      <section aria-labelledby="mem-t" class="cartao cartao-g">
        <h2 id="mem-t">Pessoas</h2>
        @if (equipe() === null) {
          <p class="carregando">Carregando…</p>
        } @else {
          <div class="tabela-rolagem">
            <table class="tabela">
              <thead><tr><th scope="col">Nome</th><th scope="col">Papel</th><th scope="col">Na equipe desde</th><th scope="col">Situação</th></tr></thead>
              <tbody>
                @for (p of equipe(); track p.usuario_id) {
                  <tr>
                    <td><strong class="bloco">{{ p.nome }}{{ p.usuario_id === auth.usuarioId() ? ' (você)' : '' }}</strong><span class="ajuda">{{ p.email }}</span></td>
                    <td>{{ PAPEL[p.papel] }}</td>
                    <td class="mono">{{ data(p.desde) }}</td>
                    <td><span class="selo selo-ativa">Ativo</span></td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          <p class="ajuda">Para colocar alguém numa obra, abra a obra e use a aba Pessoas da obra.</p>
        }
      </section>
    </div>
  `,
  styles: `
    .convite { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
    .convite .campo { flex: 1 1 180px; }
    .convite .email { flex: 2 1 260px; }
    .convite .btn { flex: 1 1 160px; }
    .papeis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; font-size: 14px; }
    .papeis div { padding: 12px 14px; border-radius: var(--raio); background: var(--papel); display: flex; flex-direction: column; }
    .papeis span { color: var(--tinta-2); }
    .tabela { min-width: 560px; font-size: 15px; }
    .bloco { display: block; }
  `,
})
export class EquipeComponent implements OnInit {
  auth = inject(AuthService);
  private servico = inject(EquipeService);
  private obrasServico = inject(ObrasService);
  private avisos = inject(AvisosService);

  readonly PAPEL = PAPEL;
  readonly data = data;
  email = '';
  papel: 'encarregado' | 'cliente' = 'encarregado';
  obraId: string | null = null;
  equipe = signal<MembroDaEquipeOut[] | null>(null);
  obras = signal<ObraResumoOut[]>([]);
  enviando = signal(false);
  erro = signal<ErroDaApi | null>(null);

  /** ?papel=cliente&obra=... vindo da aba Pessoas da obra */
  readonly papelInicial = input<string | undefined>(undefined, { alias: 'papel' });
  readonly obraInicial = input<string | undefined>(undefined, { alias: 'obra' });

  ngOnInit(): void {
    if (this.papelInicial() === 'cliente' || this.papelInicial() === 'encarregado') this.papel = this.papelInicial() as 'encarregado' | 'cliente';
    if (this.obraInicial()) this.obraId = this.obraInicial()!;
    void this.carregar();
    this.obrasServico.listar(null, 1, 100).then((r) => this.obras.set(r.itens)).catch(() => undefined);
  }

  private async carregar(): Promise<void> {
    try {
      this.equipe.set(await this.servico.equipe());
    } catch (e) {
      this.avisos.erro(mensagemDe(e));
      this.equipe.set([]);
    }
  }

  async convidar(): Promise<void> {
    this.enviando.set(true);
    this.erro.set(null);
    try {
      const c = await this.servico.convidar(this.email.trim(), this.papel, this.obraId);
      this.avisos.sucesso(`Convite enviado para ${c.email}. Ele vale por 72 horas.`);
      this.email = '';
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    } finally {
      this.enviando.set(false);
    }
  }
}
