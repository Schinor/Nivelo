import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Perfil {
  usuario_id: number;
  nome: string;
  bio: string | null;
  /** URL relativa (/storage/...), pré-assinada e com expiração; null sem foto */
  foto_url: string | null;
  /** Só para a UI: quem garante a regra de dono é o backend */
  pode_editar: boolean;
  /** Selo visual; os limites do plano são garantidos pelo backend */
  premium: boolean;
}

@Injectable({ providedIn: 'root' })
export class PerfilService {
  constructor(private http: HttpClient) {}

  getMeu(): Observable<Perfil> {
    return this.http.get<Perfil>('/api/perfis/me');
  }

  get(id: number): Observable<Perfil> {
    return this.http.get<Perfil>(`/api/perfis/${id}`);
  }

  atualizarBio(id: number, bio: string): Observable<Perfil> {
    return this.http.put<Perfil>(`/api/perfis/${id}`, { bio });
  }

  enviarFoto(id: number, arquivo: File): Observable<Perfil> {
    const form = new FormData();
    form.append('foto', arquivo);
    return this.http.put<Perfil>(`/api/perfis/${id}/foto`, form);
  }

  removerFoto(id: number): Observable<void> {
    return this.http.delete<void>(`/api/perfis/${id}/foto`);
  }
}
