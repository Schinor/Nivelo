import { Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ObraIn } from '../../api/models/obra-in';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { hoje } from '../../shared/formatos';
import { ObrasService } from './obras.service';

const UFS = 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(' ');

/** Criar (sem `obraId`) ou editar uma obra. Só o dono chega aqui (guard) e a API confere. */
@Component({
  selector: 'app-obra-form',
  imports: [FormsModule, RouterLink],
  template: `
    <main class="pagina">
      <a class="voltar" [routerLink]="obraId() ? ['/obras', obraId()] : ['/obras']">← Voltar</a>
      <h1>{{ obraId() ? 'Editar obra' : 'Nova obra' }}</h1>

      @if (carregando()) {
        <p class="carregando">Carregando…</p>
      } @else {
        <form class="formulario" (ngSubmit)="salvar()" #f="ngForm">
          <div class="campo" [class.invalido]="campo('nome')">
            <label for="nome">Nome da obra</label>
            <input id="nome" name="nome" [(ngModel)]="obra.nome" required maxlength="160" placeholder="Ex.: Reforma da casa do Jorge" />
            @if (campo('nome')) { <span class="erro-campo">{{ campo('nome') }}</span> }
          </div>
          <div class="campo">
            <label for="cliente">Cliente</label>
            <input id="cliente" name="cliente" [(ngModel)]="obra.cliente_nome" required maxlength="160" placeholder="Quem contratou a obra" />
          </div>
          <div class="campo">
            <label for="logradouro">Endereço</label>
            <input id="logradouro" name="logradouro" [(ngModel)]="obra.endereco.logradouro" required maxlength="200" placeholder="Rua e número" autocomplete="street-address" />
          </div>
          <div class="duas-colunas cidade">
            <div class="campo">
              <label for="cidade">Cidade</label>
              <input id="cidade" name="cidade" [(ngModel)]="obra.endereco.cidade" required maxlength="120" autocomplete="address-level2" />
            </div>
            <div class="campo">
              <label for="uf">UF</label>
              <select id="uf" name="uf" [(ngModel)]="obra.endereco.uf" required>
                @for (uf of ufs; track uf) { <option [value]="uf">{{ uf }}</option> }
              </select>
            </div>
          </div>
          <div class="duas-colunas">
            <div class="campo">
              <label for="inicio">Início</label>
              <input id="inicio" name="inicio" type="date" [(ngModel)]="obra.data_inicio" required />
            </div>
            <div class="campo" [class.invalido]="erro()?.codigo === 'obra-periodo-invalido'">
              <label for="termino">Previsão de término</label>
              <input id="termino" name="termino" type="date" [(ngModel)]="obra.previsao_termino" [min]="obra.data_inicio" required />
            </div>
          </div>

          @if (erro(); as e) {
            <div class="alerta alerta-erro" role="alert">
              {{ e.mensagem }}
              @if (e.status === 409) { <button type="button" class="btn btn-texto" (click)="recarregar()">Recarregar</button> }
            </div>
          }

          <div class="acoes-fixas">
            <button type="submit" class="btn btn-primario btn-bloco" [disabled]="salvando() || f.invalid">
              {{ salvando() ? 'Salvando…' : obraId() ? 'Salvar alterações' : 'Cadastrar obra' }}
            </button>
          </div>
        </form>
      }
    </main>
  `,
  styles: `.cidade { grid-template-columns: 1fr 96px; } h1 { margin-bottom: var(--space-4); }`,
})
export class ObraFormComponent implements OnInit {
  /** Parâmetro da rota (/obras/:obraId/editar); ausente ao criar. */
  readonly obraId = input<string>();

  private servico = inject(ObrasService);
  private router = inject(Router);
  private avisos = inject(AvisosService);

  readonly ufs = UFS;
  obra: ObraIn = {
    nome: '',
    cliente_nome: '',
    endereco: { logradouro: '', cidade: '', uf: 'SP' },
    data_inicio: hoje(),
    previsao_termino: '',
  };
  private versao = 0;
  carregando = signal(false);
  salvando = signal(false);
  erro = signal<ErroDaApi | null>(null);

  ngOnInit(): void {
    if (this.obraId()) void this.recarregar();
  }

  campo(nome: string): string | null {
    return this.erro()?.campo(nome) ?? null;
  }

  async recarregar(): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    try {
      const o = await this.servico.detalhar(this.obraId()!);
      this.versao = o.versao;
      this.obra = {
        nome: o.nome,
        cliente_nome: o.cliente_nome,
        endereco: { logradouro: o.endereco.logradouro, cidade: o.endereco.cidade, uf: o.endereco.uf },
        data_inicio: o.data_inicio,
        previsao_termino: o.previsao_termino,
      };
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    } finally {
      this.carregando.set(false);
    }
  }

  async salvar(): Promise<void> {
    this.salvando.set(true);
    this.erro.set(null);
    try {
      const id = this.obraId();
      const salva = id ? await this.servico.editar(id, this.versao, this.obra) : await this.servico.criar(this.obra);
      this.avisos.sucesso(id ? 'Obra atualizada.' : 'Obra cadastrada.');
      await this.router.navigate(['/obras', salva.id]);
    } catch (e) {
      const erro = paraErroDaApi(e);
      // O 402 já abriu o modal "Limite do plano"; aqui fica só o texto
      this.erro.set(erro);
    } finally {
      this.salvando.set(false);
    }
  }
}
