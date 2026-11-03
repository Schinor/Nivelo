import { Injectable, signal, computed } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface Usuario {
  id: number;
  nome: string;
  email: string;
  admin?: boolean;
  role?: string;
  role_id?: number;
  permissions?: string[];
  premium?: boolean;
  premium_desde?: string | null;
}

/** Empresa ativa do token. null = token sem tenant (usuário ainda sem empresa). */
export interface Contexto {
  empresa_id: string;
  empresa_nome: string;
  papel: 'dono' | 'encarregado' | 'cliente';
}

export interface Token {
  access_token: string;
  token_type: string;
  user?: Usuario;
  contexto?: Contexto | null;
}

export interface Cadastro {
  nome: string;
  email: string;
  senha: string;
  empresa_nome: string;
  tipo_pessoa: 'PF' | 'PJ';
  documento: string | null;
}

export interface ForgotPasswordResponse {
  message: string;
}

export interface ResetPasswordResponse {
  message: string;
}

export interface ValidateTokenResponse {
  valid: boolean;
  email?: string;
  message?: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly TOKEN_KEY = 'nivelo_token';
  private readonly USER_KEY = 'nivelo_user';

  private _token = signal<string | null>(localStorage.getItem(this.TOKEN_KEY));
  private _user = signal<Usuario | null>(
    JSON.parse(localStorage.getItem(this.USER_KEY) || 'null')
  );

  readonly token = this._token.asReadonly();
  readonly user = this._user.asReadonly();
  readonly isLoggedIn = computed(() => !!this._token());
  readonly isAdmin = computed(() => this._user()?.role === 'admin' || this.hasPermission('administrar:sistema'));
  readonly permissions = computed(() => this._user()?.permissions || []);

  constructor(private http: HttpClient) {
    if (this._token()) {
      // Adiado: o interceptor injeta o AuthService, e chamá-lo ainda dentro do
      // construtor gera NG0200 (dependência circular), o que apagava a sessão a cada F5
      queueMicrotask(() => this.carregarPerfil());
    }
  }

  hasPermission(permission: string): boolean {
    const user = this._user();
    if (!user) return false;
    const perms = user.permissions || [];
    return perms.includes(permission) || perms.includes('administrar:sistema');
  }

  hasAnyPermission(permissions: string[]): boolean {
    return permissions.some((p) => this.hasPermission(p));
  }

  /** Cria a empresa, o usuário e o vínculo de dono. O papel nunca é enviado: é sempre dono. */
  cadastrar(dados: Cadastro): Observable<unknown> {
    return this.http.post('/api/auth/cadastro', dados);
  }

  login(email: string, senha: string): Observable<Token> {
    const body = new HttpParams()
      .set('username', email.trim())
      .set('password', senha);

    return this.http
      .post<Token>('/api/auth/login', body.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      .pipe(
        tap((res) => {
          this._token.set(res.access_token);
          localStorage.setItem(this.TOKEN_KEY, res.access_token);
          if (res.user) {
            this._user.set(res.user);
            localStorage.setItem(this.USER_KEY, JSON.stringify(res.user));
          } else {
            this.carregarPerfil();
          }
        })
      );
  }

  carregarPerfil(): void {
    this.http.get<Usuario>('/api/auth/me').subscribe({
      next: (user) => {
        this._user.set(user);
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
      },
      error: () => {
        // Se o token estiver expirado ou inválido, limpa a sessão
        this.limparSessao();
      },
    });
  }

  esqueciSenha(email: string): Observable<ForgotPasswordResponse> {
    return this.http.post<ForgotPasswordResponse>('/api/auth/forgot-password', {
      email: email.trim(),
    });
  }

  validarTokenReset(token: string): Observable<ValidateTokenResponse> {
    return this.http.get<ValidateTokenResponse>(`/api/auth/validate-reset-token/${encodeURIComponent(token)}`);
  }

  redefinirSenha(token: string, novaSenha: string): Observable<ResetPasswordResponse> {
    return this.http.post<ResetPasswordResponse>('/api/auth/reset-password', {
      token,
      nova_senha: novaSenha,
    });
  }

  /** Avisa o servidor (trilha de auditoria) e limpa a sessão local, mesmo que o aviso falhe. */
  logout(): void {
    const token = this._token();
    if (token) {
      this.http
        .post<void>('/api/auth/logout', {}, { headers: { Authorization: `Bearer ${token}` } })
        .subscribe({ error: () => {} });
    }
    this.limparSessao();
  }

  /** Limpa somente o estado local (usado quando o servidor já rejeitou o token). */
  limparSessao(): void {
    this._token.set(null);
    this._user.set(null);
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  }
}
