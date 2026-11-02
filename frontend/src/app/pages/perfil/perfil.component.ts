import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { PerfilService, Perfil } from '../../services/perfil.service';
import { PremiumCtaComponent } from '../../components/premium-cta/premium-cta.component';

const BIO_MAX = 280;
const FOTO_MAX_BYTES = 2 * 1024 * 1024;
const TIPOS_ACEITOS = ['image/jpeg', 'image/png', 'image/webp'];

@Component({
  selector: 'app-perfil',
  imports: [RouterLink, FormsModule, PremiumCtaComponent],
  templateUrl: './perfil.component.html',
  styleUrl: './perfil.component.css',
})
export class PerfilComponent implements OnInit, OnDestroy {
  private perfilService = inject(PerfilService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private sub?: Subscription;

  readonly bioMax = BIO_MAX;
  readonly tiposAceitos = TIPOS_ACEITOS.join(',');

  perfil = signal<Perfil | null>(null);
  carregando = signal(true);
  erro = signal<string | null>(null);
  editando = signal(false);
  salvando = signal(false);
  bioRascunho = signal('');
  arquivo = signal<File | null>(null);
  preview = signal<string | null>(null);
  erroEdicao = signal<string | null>(null);

  inicial = computed(() => (this.perfil()?.nome || '?').trim().charAt(0).toUpperCase());

  // Evita loop: a URL assinada é recarregada no máximo uma vez por perfil carregado
  private recarregouFoto = false;

  ngOnInit() {
    this.sub = this.route.paramMap.subscribe((params) => {
      const id = params.get('id');
      if (id) {
        this.carregar(Number(id));
      } else {
        // /perfil → /perfil/<meu id>
        this.perfilService.getMeu().subscribe({
          next: (p) => this.router.navigate(['/perfil', p.usuario_id], { replaceUrl: true }),
          error: (e) => this.falhaAoCarregar(e),
        });
      }
    });
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    this.limparPreview();
  }

  carregar(id: number, manterEstado = false) {
    if (!manterEstado) {
      this.carregando.set(true);
      this.cancelarEdicao();
      this.recarregouFoto = false;
    }
    this.erro.set(null);
    this.perfilService.get(id).subscribe({
      next: (p) => {
        this.perfil.set(p);
        this.carregando.set(false);
      },
      error: (e) => this.falhaAoCarregar(e),
    });
  }

  private falhaAoCarregar(e: HttpErrorResponse) {
    this.carregando.set(false);
    this.erro.set(e.status === 404 ? 'Usuário não encontrado.' : 'Não foi possível carregar o perfil.');
  }

  /** A URL pré-assinada expira; se a página ficou aberta muito tempo, busca uma nova (uma vez). */
  onFotoErro() {
    const p = this.perfil();
    if (!p || this.recarregouFoto) return;
    this.recarregouFoto = true;
    this.carregar(p.usuario_id, true);
  }

  iniciarEdicao() {
    this.bioRascunho.set(this.perfil()?.bio || '');
    this.erroEdicao.set(null);
    this.editando.set(true);
  }

  cancelarEdicao() {
    this.editando.set(false);
    this.erroEdicao.set(null);
    this.arquivo.set(null);
    this.limparPreview();
  }

  selecionarArquivo(event: Event) {
    const input = event.target as HTMLInputElement;
    const arquivo = input.files?.[0] || null;
    this.erroEdicao.set(null);
    this.limparPreview();
    this.arquivo.set(null);
    if (!arquivo) return;

    // Pré-validação só de UX — quem garante tipo e tamanho é o backend
    if (!TIPOS_ACEITOS.includes(arquivo.type)) {
      this.erroEdicao.set('Formato não suportado. Envie JPEG, PNG ou WEBP.');
      input.value = '';
      return;
    }
    if (arquivo.size > FOTO_MAX_BYTES) {
      this.erroEdicao.set('Imagem maior que 2 MB.');
      input.value = '';
      return;
    }
    this.arquivo.set(arquivo);
    this.preview.set(URL.createObjectURL(arquivo));
  }

  salvar() {
    const p = this.perfil();
    if (!p) return;
    this.salvando.set(true);
    this.erroEdicao.set(null);

    this.perfilService.atualizarBio(p.usuario_id, this.bioRascunho()).subscribe({
      next: (atualizado) => {
        const arquivo = this.arquivo();
        if (!arquivo) {
          this.concluir(atualizado);
          return;
        }
        this.perfilService.enviarFoto(p.usuario_id, arquivo).subscribe({
          next: (comFoto) => this.concluir(comFoto),
          error: (e) => {
            // A bio já foi salva; mostra o novo estado e mantém o editor aberto com o erro
            this.perfil.set(atualizado);
            this.falhaAoSalvar(e);
          },
        });
      },
      error: (e) => this.falhaAoSalvar(e),
    });
  }

  removerFoto() {
    const p = this.perfil();
    if (!p) return;
    this.salvando.set(true);
    this.perfilService.removerFoto(p.usuario_id).subscribe({
      next: () => {
        this.perfil.set({ ...p, foto_url: null });
        this.salvando.set(false);
      },
      error: (e) => this.falhaAoSalvar(e),
    });
  }

  private concluir(perfil: Perfil) {
    this.perfil.set(perfil);
    this.salvando.set(false);
    this.recarregouFoto = false;
    this.cancelarEdicao();
  }

  private falhaAoSalvar(e: HttpErrorResponse) {
    this.salvando.set(false);
    const mensagens: Record<number, string> = {
      403: 'Você só pode editar o próprio perfil.',
      413: 'Imagem maior que 2 MB.',
      415: 'Formato não suportado. Envie JPEG, PNG ou WEBP.',
      422: `A bio pode ter no máximo ${BIO_MAX} caracteres.`,
      429: 'Muitos envios de foto; aguarde um minuto.',
      502: 'Armazenamento indisponível, tente novamente.',
    };
    this.erroEdicao.set(mensagens[e.status] || 'Não foi possível salvar o perfil.');
  }

  private limparPreview() {
    const url = this.preview();
    if (url) URL.revokeObjectURL(url);
    this.preview.set(null);
  }
}
