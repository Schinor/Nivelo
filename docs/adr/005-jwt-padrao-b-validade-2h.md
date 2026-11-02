# ADR 005 — JWT validado localmente (Padrão B), validade de 2 h

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

O `auth-service` assina o JWT (HS256) e a API o valida localmente com a mesma chave, sem chamar o `auth-service` a cada requisição (Padrão B). Isso é rápido, mas o token carrega o papel: se o papel mudar, o token antigo continua valendo até expirar. O sistema herdado usa 24 h e não tem refresh token. Um access token de 15 min sem refresh derrubaria o usuário do canteiro a cada 15 min.

## Decisão

- Claims: `sub`, `empresa_id` e `papel` do vínculo ativo, e `admin`.
- **Validade de 2 h, sem refresh token, até 13/11.**
- O **plano nunca vai no token**: é lido do banco a cada requisição (ver ADR 006).
- Depois de 13/11 entra o refresh token rotativo: access de 15 min e refresh de 30 dias em cookie `httpOnly`, guardado como hash, com rotação e revogação.

## Consequências

- Uma troca de papel ou a desativação de um vínculo leva até 2 h para valer num token já emitido. É o trade-off aceito até o refresh token existir.
- Quem passa o dia no canteiro faz login de novo algumas vezes por dia.
- A API não depende do `auth-service` para autenticar cada requisição, então segue respondendo se ele estiver lento.
