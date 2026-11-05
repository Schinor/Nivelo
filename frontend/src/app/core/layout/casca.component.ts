import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { IconeComponent, NomeDoIcone } from '../../shared/icone.component';
import { MarcaComponent } from '../../shared/marca.component';
import { PAPEL, iniciais } from '../../shared/formatos';
import { AuthService } from '../auth.service';

interface ItemDoMenu {
  rota: string;
  rotulo: string;
  curto: string;
  icone: NomeDoIcone;
}

/**
 * Casca das telas logadas: barra lateral escura no computador; no celular, barra superior com a
 * empresa ativa e navegação inferior com botões grandes. O menu segue o papel do vínculo ativo
 * (conforto: quem decide é a API).
 */
@Component({
  selector: 'app-casca',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, IconeComponent, MarcaComponent],
  template: `
    <div class="casca">
      <aside class="lateral" aria-label="Menu">
        <a routerLink="/" class="marca"><app-marca [escuro]="true" [pequena]="true" /></a>
        @if (empresa(); as e) {
          <a class="empresa" routerLink="/conta" fragment="empresas" [attr.aria-label]="'Empresa ativa: ' + e.nome + '. Ver suas empresas'">
            <span class="sigla">{{ e.sigla }}</span>
            <span class="empresa-texto"><strong>{{ e.nome }}</strong><span>{{ e.papel }}</span></span>
            <app-icone nome="trocar" [tamanho]="16" />
          </a>
        }
        <nav aria-label="Aplicativo" class="menu">
          @for (i of itens(); track i.rota) {
            <a [routerLink]="i.rota" routerLinkActive="ativo" ariaCurrentWhenActive="page"><app-icone [nome]="i.icone" />{{ i.rotulo }}</a>
          }
        </nav>
        <button type="button" class="sair" (click)="sair()"><app-icone nome="sair" />Sair</button>
      </aside>

      <header class="topo">
        <a routerLink="/" aria-label="Nivelo, página inicial"><app-marca [escuro]="true" [pequena]="true" /></a>
        @if (empresa(); as e) {
          <a class="empresa-chip" routerLink="/conta" fragment="empresas" [attr.aria-label]="'Empresa ativa: ' + e.nome">
            <span class="sigla">{{ e.sigla }}</span><span class="nome-curto">{{ e.nome }}</span>
          </a>
        }
      </header>

      <main class="conteudo" id="conteudo">
        <router-outlet />
      </main>

      <nav class="inferior" aria-label="Aplicativo" [style.--itens]="itens().length">
        @for (i of itens(); track i.rota) {
          <a [routerLink]="i.rota" routerLinkActive="ativo" ariaCurrentWhenActive="page"><app-icone [nome]="i.icone" [tamanho]="22" />{{ i.curto }}</a>
        }
      </nav>
    </div>
  `,
  styles: `
    .casca { min-height: 100vh; display: flex; flex-direction: column; }
    .conteudo { flex: 1; min-width: 0; padding: 20px 16px calc(var(--nav-inferior) + 24px); }

    .lateral { display: none; }
    .topo { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 12px 16px; background: var(--escuro); color: var(--escuro-tinta); }
    .topo > a:first-child { text-decoration: none; display: inline-flex; min-height: 44px; align-items: center; }
    .empresa-chip { display: flex; align-items: center; gap: 8px; min-height: 44px; max-width: 60%; padding: 0 10px; border: 1px solid var(--escuro-linha);
      border-radius: var(--raio); background: var(--escuro-2); color: var(--escuro-tinta); text-decoration: none; font-size: 14px; }
    .empresa-chip:hover { color: var(--escuro-tinta); }
    .nome-curto { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sigla { width: 26px; height: 26px; border-radius: 7px; background: var(--ambar); color: var(--tinta); display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 11px; flex: none; }

    .inferior { position: fixed; left: 0; right: 0; bottom: 0; z-index: 20; display: grid; grid-template-columns: repeat(var(--itens, 4), minmax(0, 1fr));
      height: var(--nav-inferior); padding: 6px 4px 10px; background: var(--branco); border-top: 1px solid var(--linha); }
    .inferior a { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; min-height: 56px; color: var(--tinta-2);
      text-decoration: none; font-size: 12px; }
    .inferior a.ativo { color: var(--verde-escuro); font-weight: 600; }

    @media (min-width: 900px) {
      .casca { flex-direction: row; }
      .topo, .inferior { display: none; }
      .conteudo { padding: 32px; }
      .lateral { display: flex; flex-direction: column; gap: 24px; position: sticky; top: 0; height: 100vh; width: 248px; flex: none;
        padding: 24px 16px; background: var(--escuro); color: var(--escuro-tinta); overflow-y: auto; }
      .marca { text-decoration: none; padding: 0 8px; display: inline-flex; }
      .empresa { display: flex; align-items: center; gap: 10px; padding: 10px; min-height: 52px; border-radius: var(--raio); border: 1px solid var(--escuro-linha);
        background: var(--escuro-2); color: var(--escuro-tinta); text-decoration: none; }
      .empresa:hover { color: var(--escuro-tinta); border-color: var(--tinta-3); }
      .empresa .sigla { width: 32px; height: 32px; border-radius: 8px; font-size: 13px; }
      .empresa-texto { display: flex; flex-direction: column; min-width: 0; flex: 1; }
      .empresa-texto strong { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .empresa-texto span { font-size: 12px; color: var(--escuro-tinta-2); }
      .menu { display: flex; flex-direction: column; gap: 4px; }
      .menu a, .sair { display: flex; align-items: center; gap: 12px; padding: 10px 12px; min-height: 44px; border-radius: var(--raio-p);
        color: var(--escuro-tinta-3); text-decoration: none; border: 0; background: transparent; text-align: left; }
      .menu a:hover, .sair:hover { background: var(--escuro-2); color: var(--escuro-tinta); }
      .menu a.ativo { background: var(--papel); color: var(--tinta); font-weight: 600; }
      .sair { margin-top: auto; }
    }
  `,
})
export class CascaComponent {
  private auth = inject(AuthService);
  private router = inject(Router);

  readonly empresa = computed(() => {
    if (this.auth.isAdmin()) return { nome: 'Nivelo', papel: 'Admin da plataforma', sigla: 'NV' };
    const ctx = this.auth.contexto();
    if (!ctx) return null;
    return { nome: ctx.empresa_nome, papel: PAPEL[ctx.papel] ?? ctx.papel, sigla: iniciais(ctx.empresa_nome) };
  });

  readonly itens = computed<ItemDoMenu[]>(() => {
    const itens: ItemDoMenu[] = [];
    if (this.auth.isAdmin()) {
      itens.push({ rota: '/usuarios', rotulo: 'Usuários', curto: 'Usuários', icone: 'admin' });
    } else {
      itens.push({ rota: '/obras', rotulo: 'Obras', curto: 'Obras', icone: 'obras' });
    }
    if (this.auth.ehDono()) {
      itens.push({ rota: '/equipe', rotulo: 'Equipe', curto: 'Equipe', icone: 'equipe' });
      itens.push({ rota: '/assinatura', rotulo: 'Assinatura', curto: 'Assinatura', icone: 'assinatura' });
    }
    itens.push({ rota: '/conta', rotulo: 'Minha conta', curto: 'Conta', icone: 'conta' });
    return itens;
  });

  sair(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
