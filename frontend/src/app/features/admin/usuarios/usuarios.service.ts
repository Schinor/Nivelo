import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Usuario } from '../../../core/auth.service';

export interface UsuarioAdmin extends Usuario {
  criado_em?: string;
}

/** Gestão de contas pela plataforma (só o admin). O papel de negócio fica nos vínculos das empresas. */
@Injectable({ providedIn: 'root' })
export class UsuariosService {
  constructor(private http: HttpClient) {}

  listar(): Observable<UsuarioAdmin[]> {
    return this.http.get<UsuarioAdmin[]>('/api/auth/users');
  }

  remover(userId: number): Observable<void> {
    return this.http.delete<void>(`/api/auth/users/${userId}`);
  }
}
