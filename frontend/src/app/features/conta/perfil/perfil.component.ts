import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService, Vinculo } from '../../../core/auth.service';
import { AvisosService } from '../../../core/avisos.service';
import { ErroDaApi, mensagemDe } from '../../../core/http/erro-da-api';
import { iniciais, PAPEL } from '../../../shared/formatos';
import { Perfil, PerfilService } from './perfil.service';

const BIO_MAX = 280;
const FOTO_MAX_BYTES = 2 * 1024 * 1024;
const TIPOS_ACEITOS = ['image/jpeg', 'image/png', 'image/webp'];

/** Minha conta: foto e apresentação, senha (por link no e-mail), empresas em que participa e sair. */
@Component({
  selector: 'app-perfil',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, FormsModule],
  template: `
    <div class="pagina pagina-estreita">
      <h1>Minha conta</h1>

      <section aria-labelledby="perfil-t" class="cartao cartao-g">
        <h2 id="perfil-t">Perfil</h2>
        @if (carregando()) {
          <p class="carregando">Carregando…</p>
        } @else {
          <div class="foto">
            @if (perfil()?.foto_url; as url) {
              <img class="retrato" [src]="url" [alt]="'Foto de ' + nome()" (error)="onFotoErro()" />
            } @else {
              <span class="retrato" aria-hidden="true">{{ iniciais(nome()) }}</span>
            }
            <div class="foto-acoes">
              <div class="acoes">
                <label class="btn btn-contorno btn-pequeno">
                  {{ salvando() ? 'Enviando…' : perfil()?.foto_url ? 'Trocar foto' : 'Enviar foto' }}
                  <input type="file" class="sr-only" [accept]="tiposAceitos" (change)="trocarFoto($event)" [disabled]="salvando()" />
                </label>
                @if (perfil()?.foto_url) {
                  <button type="button" class="btn btn-texto btn-pequeno" (click)="removerFoto()" [disabled]="salvando()">Remover</button>
                }
              </div>
              <span class="ajuda">JPG, PNG ou WEBP, até 2 MB. Aparece para a sua equipe.</span>
            </div>
          </div>
          <div class="duas-colunas">
            <div class="campo">
              <label for="nome">Nome</label>
              <input id="nome" [value]="nome()" readonly aria-describedby="fixo-ajuda" />
            </div>
            <div class="campo">
              <label for="email">E-mail</label>
              <input id="email" [value]="auth.user()?.email ?? ''" readonly aria-describedby="fixo-ajuda" />
            </div>
          </div>
          <span id="fixo-ajuda" class="ajuda">Nome e e-mail são os do cadastro.</span>
          <form class="formulario" (ngSubmit)="salvarBio()">
            <div class="campo">
              <label for="bio">Sobre você <span class="opcional">(opcional)</span></label>
              <textarea id="bio" name="bio" rows="2" [maxLength]="bioMax" [(ngModel)]="bio" placeholder="Ex.: mestre de obras há 15 anos, especialista em reformas"></textarea>
              <span class="ajuda">{{ bio.length }}/{{ bioMax }}</span>
            </div>
            @if (erroPerfil()) { <p class="alerta alerta-erro" role="alert">{{ erroPerfil() }}</p> }
            <button type="submit" class="btn btn-primario direita" [disabled]="salvando() || bio === (perfil()?.bio ?? '')">Salvar perfil</button>
          </form>
        }
      </section>

      <section aria-labelledby="senha-t" class="cartao cartao-g">
        <h2 id="senha-t">Trocar senha</h2>
        <p class="sub">Enviamos um link para {{ auth.user()?.email }}. Ele vale por 30 minutos e só pode ser usado uma vez.</p>
        <button type="button" class="btn btn-contorno esquerda" (click)="pedirTrocaDeSenha()" [disabled]="enviandoSenha() || senhaPedida()">
          {{ senhaPedida() ? 'Link enviado' : enviandoSenha() ? 'Enviando…' : 'Enviar link para trocar a senha' }}
        </button>
      </section>

      @if (!auth.isAdmin()) {
        <section aria-labelledby="vinc-t" class="cartao cartao-g" id="empresas">
          <h2 id="vinc-t">Empresas em que você participa</h2>
          @if (vinculos() === null) {
            <p class="carregando">Carregando…</p>
          } @else {
            @for (v of vinculos(); track v.empresa_id) {
              <div class="empresa">
                <span class="sigla" aria-hidden="true">{{ iniciais(v.empresa_nome) }}</span>
                <div><strong>{{ v.empresa_nome }}</strong><span>{{ PAPEL[v.papel] }} · {{ v.tipo_pessoa === 'PF' ? 'autônomo' : 'empresa' }}</span></div>
                @if (v.empresa_id === auth.contexto()?.empresa_id) {
                  <span class="selo selo-atual">Atual</span>
                } @else {
                  <button type="button" class="btn btn-pequeno" (click)="trocar(v)" [disabled]="trocando()">Usar esta</button>
                }
              </div>
            } @empty {
              <p class="ajuda">Você ainda não participa de nenhuma empresa.</p>
            }
          }
          <a routerLink="/empresas/nova" class="link-acao">Criar outra empresa</a>
        </section>
      }

      <section class="cartao cartao-g sair">
        <div><strong>Sair</strong><span class="sub">Encerra o acesso neste aparelho.</span></div>
        <button type="button" class="btn" (click)="sair()">Sair da conta</button>
      </section>
    </div>
  `,
  styles: `
    .foto { display: flex; flex-wrap: wrap; align-items: center; gap: 20px; }
    .retrato { width: 88px; height: 88px; border-radius: 44px; background: var(--verde-claro); color: var(--verde-escuro); display: flex; align-items: center;
      justify-content: center; font-family: var(--fonte-titulo); font-weight: 700; font-size: 30px; object-fit: cover; flex: none; }
    .foto-acoes { display: flex; flex-direction: column; gap: 8px; }
    label.btn { cursor: pointer; }
    .campo input[readonly] { background: var(--papel); color: var(--tinta-2); }
    .direita { align-self: flex-end; }
    .esquerda { align-self: flex-start; }
    .empresa { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--linha-suave); }
    .empresa > div { flex: 1; display: flex; flex-direction: column; min-width: 0; }
    .empresa > div span { font-size: 13px; color: var(--tinta-3); }
    .sigla { width: 36px; height: 36px; border-radius: 9px; background: var(--ambar); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; flex: none; }
    .link-acao { font-weight: 600; font-size: 14px; min-height: 40px; display: inline-flex; align-items: center; align-self: flex-start; }
    .sair { flex-direction: row; flex-wrap: wrap; align-items: center; justify-content: space-between; background: transparent; }
    .sair > div { display: flex; flex-direction: column; }
  `,
})
export class PerfilComponent implements OnInit, OnDestroy {
  auth = inject(AuthService);
  private perfilService = inject(PerfilService);
  private avisos = inject(AvisosService);
  private router = inject(Router);

  readonly bioMax = BIO_MAX;
  readonly tiposAceitos = TIPOS_ACEITOS.join(',');
  readonly iniciais = iniciais;
  readonly PAPEL = PAPEL;

  perfil = signal<Perfil | null>(null);
  carregando = signal(true);
  salvando = signal(false);
  erroPerfil = signal<string | null>(null);
  bio = '';
  vinculos = signal<Vinculo[] | null>(null);
  trocando = signal(false);
  enviandoSenha = signal(false);
  senhaPedida = signal(false);
  readonly nome = computed(() => this.perfil()?.nome ?? this.auth.user()?.nome ?? '');

  // A URL assinada da foto expira: recarrega no máximo uma vez por perfil carregado
  private recarregouFoto = false;

  ngOnInit(): void {
    this.carregar();
    if (!this.auth.isAdmin()) {
      this.auth.vinculos().subscribe({ next: (v) => this.vinculos.set(v), error: () => this.vinculos.set([]) });
    }
  }

  ngOnDestroy(): void {
    this.recarregouFoto = true;
  }

  private carregar(): void {
    this.perfilService.getMeu().subscribe({
      next: (p) => {
        this.perfil.set(p);
        this.bio = p.bio ?? '';
        this.carregando.set(false);
      },
      error: () => {
        this.carregando.set(false);
        this.erroPerfil.set('Não foi possível carregar o perfil.');
      },
    });
  }

  onFotoErro(): void {
    if (this.recarregouFoto) return;
    this.recarregouFoto = true;
    this.carregar();
  }

  salvarBio(): void {
    const p = this.perfil();
    if (!p) return;
    this.salvando.set(true);
    this.erroPerfil.set(null);
    this.perfilService.atualizarBio(p.usuario_id, this.bio.trim()).subscribe({
      next: (atualizado) => {
        this.perfil.set(atualizado);
        this.salvando.set(false);
        this.avisos.sucesso('Perfil salvo.');
      },
      error: (e) => this.falha(e),
    });
  }

  trocarFoto(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const arquivo = campo.files?.[0];
    campo.value = '';
    const p = this.perfil();
    if (!arquivo || !p) return;
    // Pré-validação só de conforto: quem garante tipo e tamanho é o backend
    if (!TIPOS_ACEITOS.includes(arquivo.type)) return this.erroPerfil.set('Formato não suportado. Envie JPG, PNG ou WEBP.');
    if (arquivo.size > FOTO_MAX_BYTES) return this.erroPerfil.set('A imagem passa de 2 MB.');
    this.salvando.set(true);
    this.erroPerfil.set(null);
    this.perfilService.enviarFoto(p.usuario_id, arquivo).subscribe({
      next: (atualizado) => {
        this.recarregouFoto = false;
        this.perfil.set(atualizado);
        this.salvando.set(false);
      },
      error: (e) => this.falha(e),
    });
  }

  removerFoto(): void {
    const p = this.perfil();
    if (!p) return;
    this.salvando.set(true);
    this.perfilService.removerFoto(p.usuario_id).subscribe({
      next: () => {
        this.perfil.set({ ...p, foto_url: null });
        this.salvando.set(false);
      },
      error: (e) => this.falha(e),
    });
  }

  pedirTrocaDeSenha(): void {
    const email = this.auth.user()?.email;
    if (!email) return;
    this.enviandoSenha.set(true);
    this.auth.esqueciSenha(email).subscribe({
      next: () => {
        this.enviandoSenha.set(false);
        this.senhaPedida.set(true);
        this.avisos.sucesso('Link enviado. Confira o seu e-mail.');
      },
      error: (e) => {
        this.enviandoSenha.set(false);
        this.avisos.erro(mensagemDe(e));
      },
    });
  }

  /** A API confere o vínculo e emite um token novo com a empresa escolhida. */
  trocar(v: Vinculo): void {
    this.trocando.set(true);
    this.auth.trocarEmpresa(v.empresa_id).subscribe({
      next: () => {
        this.trocando.set(false);
        this.avisos.sucesso(`Agora você está em ${v.empresa_nome}.`);
        void this.router.navigate(['/obras']);
      },
      error: (e) => {
        this.trocando.set(false);
        this.avisos.erro(mensagemDe(e));
      },
    });
  }

  sair(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }

  private falha(e: ErroDaApi): void {
    this.salvando.set(false);
    const mensagens: Record<number, string> = {
      413: 'A imagem passa de 2 MB.',
      415: 'Formato não suportado. Envie JPG, PNG ou WEBP.',
      422: `A apresentação pode ter no máximo ${BIO_MAX} caracteres.`,
      429: 'Muitos envios de foto; aguarde um minuto.',
      502: 'Armazenamento indisponível. Tente de novo.',
    };
    this.erroPerfil.set(mensagens[e.status] ?? e.mensagem ?? 'Não foi possível salvar o perfil.');
  }
}
