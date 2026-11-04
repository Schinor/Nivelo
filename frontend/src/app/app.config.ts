import { ApplicationConfig, LOCALE_ID, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';
import { routes } from './app.routes';
import { errosInterceptor } from './core/http/erros.interceptor';
import { tokenInterceptor } from './core/http/token.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Parâmetros de rota viram inputs tipados dos componentes (ex.: obraId)
    provideRouter(routes, withComponentInputBinding(), withInMemoryScrolling({ scrollPositionRestoration: 'top' })),
    // O de erros fica por fora: o de token ainda vê o 401 cru e limpa a sessão
    provideHttpClient(withInterceptors([errosInterceptor, tokenInterceptor])),
    { provide: LOCALE_ID, useValue: 'pt-BR' },
  ],
};
