# Navegação a 390 px (Playwright)

Roteiro que navega pelo Nivelo como num celular (390 × 844, pt-BR, fuso de São Paulo) e tira um
print de cada tela em `e2e/prints/` (fora do Git). Cada print confere que a tela não rola na
horizontal; se algo falhar, o print da tela do erro fica em `e2e/prints/erro.png`.

Roda dentro da imagem oficial do Playwright, sem instalar nada na máquina:

```bash
# 1. Dono: landing → cadastro → obra → diário com foto → publicar → foto depois da publicação
#    → revisão → convite do cliente → limite do plano (402)
e2e/rodar.sh dono --base http://localhost:8000

# 2. Cliente: pegue o token do link do convite (na stack local, no log do auth-service)
TOKEN=$(docker compose -f docker-compose.ci.yml logs auth-service | grep -o 'convite?token=[A-Za-z0-9_-]*' | tail -1 | cut -d= -f2)
e2e/rodar.sh cliente --base http://localhost:8000 --token "$TOKEN"
```

## Em produção (prints da Fase 7)

O roteiro cria contas e uma obra de verdade. Use e-mails seus, para o convite chegar numa caixa
que você lê:

```bash
e2e/rodar.sh dono --base https://<subdominio> \
  --email-dono voce+dono@gmail.com --email-cliente voce+cliente@gmail.com --senha '<senha forte>'
# abra o e-mail do convite e copie o token do link (.../convite?token=...)
e2e/rodar.sh cliente --base https://<subdominio> --token '<token>' --senha '<a mesma senha>'
```

Outras opções: `--saida`, `--nome-dono`, `--empresa`, `--nome-cliente`, `--obra`
(`python navegar.py --help`). O `estado.json` que liga os dois passos fica na pasta de saída.
