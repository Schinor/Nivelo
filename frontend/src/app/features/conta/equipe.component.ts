import { Component, OnInit, inject, signal } from '@angular/core';
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
  imports: [FormsModule],
  template: `
    <main class="pagina">
      <h1>Equipe</h1>
      <p class="sub">{{ auth.contexto()?.empresa_nome }}. Encarregados registram os diários; clientes acompanham as obras e não pagam.</p>

      <section class="cartao">
        <h2>Convidar por e-mail</h2>
        <form class="formulario" (ngSubmit)="convidar()" #f="ngForm">
          <div class="campo" [class.invalido]="erro()?.campo('email')">
            <label for="email">E-mail</label>
            <input id="email" name="email" type="email" inputmode="email" autocomplete="off" [(ngModel)]="email" required />
            @if (erro()?.campo('email')) { <span class="erro-campo">E-mail inválido.</span> }
          </div>
          <fieldset class="campo">
            <legend class="rotulo">Como essa pessoa entra</legend>
            <div class="opcoes">
              <label class="opcao"><input type="radio" name="papel" value="encarregado" [(ngModel)]="papel" /><span>Encarregado</span></label>
              <label class="opcao"><input type="radio" name="papel" value="cliente" [(ngModel)]="papel" /><span>Cliente</span></label>
            </div>
          </fieldset>
          <div class="campo">
            <label for="obra">Obra <span class="opcional">(opcional)</span></label>
            <select id="obra" name="obra" [(ngModel)]="obraId">
              <option [ngValue]="null">Nenhuma por enquanto</option>
              @for (o of obras(); track o.id) { <option [ngValue]="o.id">{{ o.nome }}</option> }
            </select>
            <span class="ajuda">Ao aceitar, a pessoa já entra nessa obra.</span>
          </div>
          @if (erro(); as e) { <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p> }
          <button type="submit" class="btn btn-primario btn-bloco" [disabled]="enviando() || f.invalid">
            {{ enviando() ? 'Enviando…' : 'Enviar convite' }}
          </button>
        </form>
      </section>

      <h2>Pessoas na empresa</h2>
      @if (equipe() === null) {
        <p class="carregando">Carregando…</p>
      } @else {
        <ul class="lista pessoas">
          @for (p of equipe(); track p.usuario_id) {
            <li class="cartao pessoa">
              <div>
                <strong>{{ p.nome }}{{ p.usuario_id === auth.usuarioId() ? ' (você)' : '' }}</strong>
                <span class="email">{{ p.email }}</span>
              </div>
              <div class="direita">
                <span class="papel">{{ PAPEL[p.papel] }}</span>
                <span class="desde">desde {{ data(p.desde) }}</span>
              </div>
            </li>
          }
        </ul>
        <p class="ajuda">Para colocar alguém numa obra, abra a obra e use “Quem acompanha a obra”.</p>
      }
    </main>
  `,
  styles: `
    .sub { color: var(--ink-muted); margin: 6px 0 var(--space-4); }
    .cartao h2 { margin-top: 0; }
    fieldset { border: 0; }
    .opcional { color: var(--ink-faint); font-weight: 400; }
    .ajuda { color: var(--ink-faint); font-size: .85rem; }
    .pessoas { list-style: none; margin-bottom: var(--space-3); }
    .pessoa { display: flex; justify-content: space-between; gap: var(--space-3); align-items: center; }
    .pessoa > div { display: grid; gap: 2px; min-width: 0; }
    .email { color: var(--ink-muted); font-size: .85rem; overflow-wrap: anywhere; }
    .direita { text-align: right; }
    .papel { font-weight: 600; }
    .desde { color: var(--ink-faint); font-size: .78rem; }
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

  ngOnInit(): void {
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
