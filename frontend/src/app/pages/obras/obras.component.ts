import { Component, inject } from '@angular/core';
import { AuthService } from '../../services/auth.service';

/** Tela provisória: a lista de obras e o diário chegam nas Fases 4 e 5. */
@Component({
  selector: 'app-obras',
  standalone: true,
  template: `
    <main class="obras-page">
      <h1>Suas obras</h1>
      <p>Olá, {{ auth.user()?.nome }}. O cadastro de obras e o diário do dia estão chegando.</p>
    </main>
  `,
  styles: `
    .obras-page { max-width: 720px; margin: 3rem auto; padding: 0 1.25rem; }
    h1 { margin-bottom: .75rem; }
    p { color: var(--text-muted, #9a9a9a); }
  `,
})
export class ObrasComponent {
  auth = inject(AuthService);
}
