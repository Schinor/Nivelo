"""Navegação do Nivelo num celular (390 px), com Playwright, tirando um print de cada tela.

Dois roteiros, em dois passos, porque o cliente só entra pelo link do convite:

- ``dono``: landing → cadastro → primeira obra → registrar o dia com foto → publicar → foto depois
  da publicação → revisão com motivo → abas da obra → convite do cliente → limite do plano (402).
- ``cliente``: aceite do convite → login → obra → diário publicado com as fotos, sem os
  controles de escrita → comentário.
- ``assinatura`` (Atividade 11): conta nova no Free → 2ª obra recusada (402) → checkout do Pro
  com o cartão 4242 → o webhook confirma → 2ª obra criada → painel do admin com o MRR → portal
  cancela → volta para o Free → MRR zerado. Só funciona com o Stripe em modo de teste.

Cada print confere que a tela não rola na horizontal. O roteiro ``dono`` grava o e-mail do
cliente e as URLs da obra e do diário em ``<saida>/estado.json``, lido pelo roteiro ``cliente``.

Uso (ver e2e/README.md):
    python navegar.py dono --base https://nivelo.exemplo --email-dono d@x --email-cliente c@x
    python navegar.py cliente --base https://nivelo.exemplo --token <token do link do convite>
    python navegar.py assinatura --base https://nivelo.exemplo --email-admin a@x --senha-admin-arquivo f
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, Playwright, expect, sync_playwright

LARGURA = 390
ALTURA = 844
UUID = r"[0-9a-f-]{36}"


class Roteiro:
    def __init__(self, args: argparse.Namespace) -> None:
        self.base = args.base.rstrip("/")
        self.saida = Path(args.saida)
        self.saida.mkdir(parents=True, exist_ok=True)
        self.estado = self.saida / "estado.json"
        self.passo = {"dono": 0, "cliente": 20, "assinatura": 40}[args.roteiro]
        self.erros_no_console: list[str] = []
        self.atual: Page | None = None

    def pagina(self, p: Playwright) -> Page:
        navegador = self.navegador = getattr(self, "navegador", None) or p.chromium.launch()
        contexto = navegador.new_context(
            viewport={"width": LARGURA, "height": ALTURA},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="pt-BR",
            # O "hoje" da API é o do fuso do negócio; sem isto, o Chromium em UTC manda o dia seguinte
            # depois das 21h e o diário volta 422 (data futura).
            timezone_id="America/Sao_Paulo",
        )
        pag = contexto.new_page()
        pag.on("console", lambda m: m.type == "error" and self.erros_no_console.append(m.text))
        self.atual = pag
        return pag

    def foto(self, pag: Page, nome: str, inteira: bool = True) -> None:
        """``inteira=False`` nas páginas do Stripe: o print da página inteira corta os iframes."""
        self.passo += 1
        pag.wait_for_timeout(400)
        pag.screenshot(path=str(self.saida / f"{self.passo:02d}-{nome}.png"), full_page=inteira)
        largura = pag.evaluate("document.documentElement.scrollWidth")
        assert largura <= LARGURA + 1, f"{nome}: rolagem horizontal ({largura}px)"
        print(f"  [ok] {self.passo:02d} {nome} (largura {largura}px)")


def jpeg(caminho: Path, cor: tuple[int, int, int]) -> None:
    """Foto grande (4000x3000), para conferir que o navegador comprime para 1600 px."""
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), cor).save(buf, "JPEG", quality=95)
    caminho.write_bytes(buf.getvalue())


def dono(r: Roteiro, p: Playwright, args: argparse.Namespace) -> None:
    pasta = Path(tempfile.mkdtemp(prefix="nivelo-e2e-"))
    canteiro, depois = pasta / "canteiro.jpg", pasta / "depois.jpg"
    jpeg(canteiro, (170, 120, 70))
    jpeg(depois, (60, 110, 160))
    pag = r.pagina(p)

    pag.goto(r.base + "/")
    expect(pag.get_by_role("heading", name="Cada dia de obra registrado. Cada cliente por dentro.")).to_be_visible()
    expect(pag.get_by_text("R$ 29,90", exact=True)).to_be_visible()
    expect(pag.get_by_text("R$ 69,90", exact=True)).to_be_visible()
    r.foto(pag, "landing")

    pag.get_by_role("link", name="Criar conta grátis").first.click()
    pag.wait_for_url("**/cadastro")
    pag.get_by_text("Autônomo", exact=True).click()
    pag.fill("#org", args.empresa)
    pag.fill("#nome", args.nome_dono)
    pag.fill("#email", args.email_dono)
    pag.fill("#senha", args.senha)
    r.foto(pag, "cadastro")
    pag.locator("form button[type=submit]").click()
    # Passo 2 de 2: o cadastro leva direto para a primeira obra
    pag.wait_for_url("**/obras/nova")
    expect(pag.get_by_text("Passo 2 de 2")).to_be_visible()
    pag.fill("#nome", args.obra)
    pag.fill("#cliente", args.nome_cliente)
    pag.fill("#logradouro", "Rua das Acácias, 120")
    pag.fill("#cidade", "Marília")
    pag.fill("#termino", "2027-03-31")
    r.foto(pag, "obra-nova")
    pag.get_by_role("button", name="Cadastrar obra").click()
    pag.wait_for_url(re.compile(rf"/obras/{UUID}$"))
    obra_url = pag.url
    expect(pag.get_by_role("heading", name=args.obra)).to_be_visible()
    r.foto(pag, "obra-detalhe")

    pag.goto(r.base + "/obras")
    expect(pag.get_by_text(args.obra).first).to_be_visible()
    r.foto(pag, "obras")
    pag.goto(obra_url)

    pag.get_by_role("link", name="Registrar o dia de hoje").first.click()
    pag.locator("fieldset", has_text="Manhã").get_by_text("Sol", exact=True).click()
    pag.locator("fieldset", has_text="Tarde").get_by_text("Chuva", exact=True).click()
    for _ in range(4):
        pag.get_by_role("button", name="Aumentar").click()
    pag.fill("#nova-at", "Demolição da parede da cozinha")
    pag.get_by_role("button", name="Adicionar atividade").click()
    pag.fill("#nova-at", "Retirada do entulho")
    pag.keyboard.press("Enter")
    expect(pag.locator(".lista-atividades li")).to_have_count(2)
    pag.get_by_text("Sim", exact=True).click()
    pag.get_by_role("button", name="Chuva", exact=True).click()
    pag.fill("#oc-desc-0", "Chuva forte às 15h, serviço externo parado")
    pag.fill("#oc-imp-0", "1")
    pag.locator("app-seletor-de-fotos input[type=file]").set_input_files(str(canteiro))
    expect(pag.locator(".previas img")).to_have_count(1)
    r.foto(pag, "diario-formulario")
    pag.get_by_role("button", name="Publicar o dia").click()
    pag.wait_for_url(re.compile(rf"/diarios/{UUID}$"))
    diario_url = pag.url
    expect(pag.locator(".selo-publicado")).to_be_visible()
    expect(pag.locator("app-galeria img")).to_have_count(1)
    pag.wait_for_function("document.querySelector('app-galeria img')?.naturalWidth > 0")
    largura_foto = pag.evaluate("document.querySelector('app-galeria img').naturalWidth")
    assert largura_foto == 1600, f"a foto não foi comprimida para 1600 px: {largura_foto}"
    r.foto(pag, "diario-publicado-com-foto")

    pag.locator("app-seletor-de-fotos input[type=file]").set_input_files(str(depois))
    # Comprimir 4000 px no navegador e enviar leva alguns segundos
    expect(pag.locator("app-galeria img")).to_have_count(2, timeout=30_000)
    expect(pag.get_by_text("Adicionada após a publicação").first).to_be_visible()
    r.foto(pag, "foto-apos-publicacao")

    pag.get_by_role("button", name="Revisar diário").click()
    pag.fill("#motivo", "Faltou contar o ajudante que chegou às 9h")
    r.foto(pag, "revisao-motivo")
    pag.get_by_role("button", name="Continuar para edição").click()
    expect(pag.locator("#motivo")).to_have_value("Faltou contar o ajudante que chegou às 9h")
    pag.get_by_role("button", name="Aumentar").click()
    r.foto(pag, "revisao-formulario")
    pag.get_by_role("button", name="Salvar revisão").click()
    pag.wait_for_url(diario_url)
    expect(pag.get_by_text("Faltou contar o ajudante").first).to_be_visible()
    expect(pag.locator(".selo-revisado")).to_be_visible()
    r.foto(pag, "diario-revisado")

    pag.goto(obra_url)
    for aba, nome in (
        ("Fotos", "obra-aba-fotos"),
        ("Ocorrências", "obra-aba-ocorrencias"),
        ("Histórico", "obra-aba-historico"),
    ):
        pag.get_by_role("tab", name=re.compile(aba)).click()
        pag.wait_for_timeout(600)
        r.foto(pag, nome)
    pag.get_by_role("tab", name=re.compile("Ocorrências")).click()
    expect(pag.get_by_text("Chuva forte às 15h")).to_be_visible()
    pag.get_by_role("tab", name=re.compile("Pessoas da obra")).click()
    r.foto(pag, "obra-aba-pessoas")
    pag.get_by_role("link", name="Convidar cliente").click()
    pag.wait_for_url("**/equipe**")
    pag.fill("#email", args.email_cliente)
    expect(pag.locator("#papel")).to_have_value("cliente")
    r.foto(pag, "equipe-convite")
    pag.get_by_role("button", name="Enviar convite").click()
    expect(pag.get_by_text("Convite enviado")).to_be_visible(timeout=30_000)

    # Free: uma obra ativa. A segunda esbarra no limite (402) e abre o modal.
    pag.goto(r.base + "/obras/nova")
    pag.fill("#nome", "Muro da escola")
    pag.fill("#cliente", "Escola")
    pag.fill("#logradouro", "Rua 2")
    pag.fill("#cidade", "Marília")
    pag.fill("#termino", "2027-01-31")
    pag.get_by_role("button", name="Cadastrar obra").click()
    expect(pag.get_by_role("dialog").get_by_text("Assinar o Pro")).to_be_visible()
    r.foto(pag, "limite-do-plano-402")

    estado = {"cliente": args.email_cliente, "obra": args.obra, "obra_url": obra_url, "diario_url": diario_url}
    r.estado.write_text(json.dumps(estado, ensure_ascii=False, indent=2))


def cliente(r: Roteiro, p: Playwright, args: argparse.Namespace) -> None:
    estado = json.loads(r.estado.read_text())
    pag = r.pagina(p)

    pag.goto(f"{r.base}/convite?token={args.token}")
    pag.fill("#nome", args.nome_cliente)
    pag.fill("#senha", args.senha)
    r.foto(pag, "convite-aceite")
    pag.get_by_role("button", name="Aceitar convite").click()
    pag.wait_for_url("**/login")
    pag.fill("#email", estado["cliente"])
    pag.fill("#senha", args.senha)
    pag.locator("form button[type=submit]").click()
    pag.wait_for_url("**/obras")
    expect(pag.get_by_text(estado["obra"]).first).to_be_visible()
    expect(pag.get_by_role("link", name="Nova obra")).to_have_count(0)
    expect(pag.get_by_role("link", name=re.compile("Registrar o dia"))).to_have_count(0)
    r.foto(pag, "cliente-obras")

    pag.get_by_text(estado["obra"]).first.click()
    expect(pag.get_by_role("link", name=re.compile("Registrar o dia"))).to_have_count(0)
    expect(pag.get_by_role("link", name="Editar obra")).to_have_count(0)
    expect(pag.get_by_role("tab", name=re.compile("Histórico"))).to_have_count(0)
    expect(pag.get_by_role("button", name=re.compile("Remover"))).to_have_count(0)
    r.foto(pag, "cliente-obra")

    pag.goto(estado["diario_url"])
    expect(pag.locator("app-galeria img")).to_have_count(2)
    pag.wait_for_function("[...document.querySelectorAll('app-galeria img')].every(i => i.naturalWidth > 0)")
    expect(pag.get_by_text("Adicionada após a publicação").first).to_be_visible()
    for proibido in ("Publicar o dia", "Revisar diário", "Adicionar fotos", "Remover rascunho"):
        assert pag.get_by_text(proibido).count() == 0, f"o cliente vê um controle de escrita: {proibido}"
    pag.fill("#comentario", "Obrigado! Pode seguir com o contrapiso quando secar.")
    pag.get_by_role("button", name="Comentar").click()
    expect(pag.get_by_text("Pode seguir com o contrapiso")).to_be_visible()
    r.foto(pag, "cliente-diario-publicado")


CARTAO_APROVADO = "4242 4242 4242 4242"
PRECO_PRO = 2990
PAGAMENTO_STRIPE = re.compile(r"^https://(checkout|billing)\.stripe\.com/")


def nova_obra(pag: Page, base: str, nome: str) -> None:
    pag.goto(base + "/obras/nova")
    pag.fill("#nome", nome)
    pag.fill("#cliente", "Cliente do roteiro")
    pag.fill("#logradouro", "Rua 2")
    pag.fill("#cidade", "Marília")
    pag.fill("#termino", "2027-01-31")
    pag.get_by_role("button", name="Cadastrar obra").click()


def plano_na_tela(pag: Page, base: str, plano: str, tempo_s: int = 60) -> None:
    """Quem muda o plano é o webhook: recarrega /assinatura até ele chegar."""
    fim = time.time() + tempo_s
    while True:
        pag.goto(base + "/assinatura")
        try:
            expect(pag.get_by_role("heading", name=f"Plano {plano}")).to_be_visible(timeout=5_000)
            return
        except AssertionError:
            if time.time() > fim:
                raise
            pag.wait_for_timeout(2_000)


def pagar_no_checkout(r: Roteiro, pag: Page, nome: str) -> None:
    """Página hospedada do Stripe (modo de teste). Cartão, nome, país e o botão "Assinar" ficam
    todos no iframe do Payment Element, que entra depois da página."""
    pag.wait_for_url(PAGAMENTO_STRIPE, timeout=30_000)
    form = pag.frame_locator("iframe[src*='elements-inner']").first
    form.locator("#payment-numberInput").fill(CARTAO_APROVADO, timeout=30_000)
    form.locator("#payment-expiryInput").fill("12 / 34")
    form.locator("#payment-cvcInput").fill("123")
    form.locator("#payment-nameInput").fill(nome)
    link = form.locator("#payment-linkOptInInput")
    if link.count() and link.is_checked():
        link.uncheck()
    form.locator("#payment-nameInput").scroll_into_view_if_needed()
    r.foto(pag, "checkout-stripe-cartao-4242", inteira=False)
    form.get_by_role("button", name=re.compile("^(Assinar|Subscribe)$")).click()


def entrar(pag: Page, base: str, email: str, senha: str) -> None:
    pag.goto(base + "/login")
    pag.fill("#email", email)
    pag.fill("#senha", senha)
    pag.locator("form button[type=submit]").click()
    pag.wait_for_url(lambda url: "/login" not in url)


def centavos(texto: str) -> int:
    return int(re.sub(r"\D", "", texto))


def reais(valor: int) -> str:
    inteiro, resto = divmod(valor, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def painel_do_admin(r: Roteiro, pag: Page, nome: str, mrr_esperado: int | None = None) -> int:
    """Devolve o MRR mostrado. Outras empresas podem estar assinando ao mesmo tempo, então o
    roteiro confere a diferença (R$ 29,90 a menos depois do cancelamento), não um valor fixo."""
    pag.goto(r.base + "/admin")
    expect(pag.get_by_role("heading", name="Painel")).to_be_visible()
    valor = pag.locator(".indicador", has_text="MRR de teste").locator(".valor")
    expect(valor).to_contain_text("R$")
    fim = time.time() + 30
    while mrr_esperado is not None and centavos(valor.inner_text()) != mrr_esperado:
        assert time.time() < fim, f"o MRR não chegou a {reais(mrr_esperado)} (está em {valor.inner_text()})"
        pag.get_by_role("button", name="Atualizar").click()
        pag.wait_for_timeout(2_000)
    expect(pag.get_by_text("assinatura.iniciada").first).to_be_visible()
    r.foto(pag, nome)
    return centavos(valor.inner_text())


def ate_o_pro(r: Roteiro, pag: Page, args: argparse.Namespace) -> None:
    pag.goto(r.base + "/cadastro")
    pag.get_by_text("Autônomo", exact=True).click()
    pag.fill("#org", args.empresa)
    pag.fill("#nome", args.nome_dono)
    pag.fill("#email", args.email_dono)
    pag.fill("#senha", args.senha)
    pag.locator("form button[type=submit]").click()
    pag.wait_for_url("**/obras/nova")
    nova_obra(pag, r.base, args.obra)
    pag.wait_for_url(re.compile(rf"/obras/{UUID}$"))

    plano_na_tela(pag, r.base, "Free", tempo_s=0)
    expect(pag.get_by_role("button", name="Assinar Pro")).to_be_visible()
    r.foto(pag, "conta-nova-no-free")

    nova_obra(pag, r.base, "Muro da escola")
    expect(pag.get_by_role("dialog").get_by_text("Assinar o Pro")).to_be_visible()
    r.foto(pag, "segunda-obra-recusada-402")

    pag.goto(r.base + "/assinatura")
    pag.get_by_role("button", name="Assinar Pro").click()
    pagar_no_checkout(r, pag, args.nome_dono)
    # A volta do checkout não muda nada: a tela espera o webhook
    pag.wait_for_url("**/assinatura?checkout=sucesso", timeout=60_000)
    # Se o webhook chegou antes da volta, a tela já abre confirmada, sem o "Confirmando…"
    expect(pag.get_by_text(re.compile("^(Confirmando pagamento|Pagamento confirmado)")).first).to_be_visible()
    r.foto(pag, "volta-do-checkout-confirmando")
    expect(pag.get_by_text("Pagamento confirmado")).to_be_visible(timeout=35_000)
    expect(pag.get_by_role("heading", name="Plano Pro")).to_be_visible()
    r.foto(pag, "plano-pro-depois-do-webhook")

    nova_obra(pag, r.base, "Muro da escola")
    pag.wait_for_url(re.compile(rf"/obras/{UUID}$"))
    expect(pag.get_by_role("heading", name="Muro da escola")).to_be_visible()
    r.foto(pag, "segunda-obra-criada-no-pro")


def assinatura(r: Roteiro, p: Playwright, args: argparse.Namespace) -> None:
    senha_admin = Path(args.senha_admin_arquivo).read_text().strip()
    pag = r.pagina(p)
    if args.retomar:
        # A conta já assinou numa rodada anterior: segue do painel do admin, sem uma 2ª assinatura
        r.passo = 46
        entrar(pag, r.base, args.email_dono, args.senha)
        plano_na_tela(pag, r.base, "Pro", tempo_s=20)
    else:
        ate_o_pro(r, pag, args)

    admin = r.pagina(p)
    entrar(admin, r.base, args.email_admin, senha_admin)
    mrr = painel_do_admin(r, admin, "painel-admin-com-a-assinatura")

    r.atual = pag
    pag.goto(r.base + "/assinatura")
    pag.get_by_role("button", name="Gerenciar assinatura").click()
    pag.wait_for_url(PAGAMENTO_STRIPE, timeout=30_000)
    renovar = pag.get_by_role("button", name=re.compile("^(Renovar|Renew)", re.I)).or_(
        pag.get_by_role("link", name=re.compile("^(Renovar|Renew)", re.I))
    )
    if renovar.count():
        # Uma rodada anterior cancelou no fim do período: reativa para cancelar de novo, na hora
        renovar.first.click()
        pag.locator("[data-testid=confirm]").click()
        expect(
            pag.get_by_role("link", name=re.compile("Cancelar (a )?assinatura|Cancel subscription", re.I))
            .or_(pag.get_by_role("button", name=re.compile("Cancelar (a )?assinatura|Cancel subscription", re.I)))
            .first
        ).to_be_visible(timeout=30_000)
    r.foto(pag, "portal-do-stripe", inteira=False)
    pag.get_by_role("link", name=re.compile("Cancelar (a )?assinatura|Cancel subscription", re.I)).or_(
        pag.get_by_role("button", name=re.compile("Cancelar (a )?assinatura|Cancel subscription", re.I))
    ).first.click()
    # O portal pede o motivo num modal e depois a confirmação; os passos variam com a configuração
    avancar = re.compile("^(Continu.*cancelamento|Cancelar (a )?assinatura|Confirmar|Cancel subscription)$", re.I)
    for _ in range(3):
        pag.wait_for_timeout(1_500)
        motivo = pag.locator("select:visible")
        if motivo.count():
            motivo.first.select_option(index=1)
        botao = pag.get_by_role("button", name=avancar).locator("visible=true")
        if not botao.count():
            break
        botao.last.click()
    expect(pag.get_by_text(re.compile("cancelad|canceled", re.I)).first).to_be_visible(timeout=30_000)
    r.foto(pag, "portal-assinatura-cancelada", inteira=False)

    plano_na_tela(pag, r.base, "Free")
    r.foto(pag, "de-volta-ao-free")

    r.atual = admin
    painel_do_admin(r, admin, "painel-admin-depois-do-cancelamento", mrr_esperado=mrr - PRECO_PRO)


def argumentos(argv: list[str]) -> argparse.Namespace:
    agora = int(time.time())
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roteiro", choices=["dono", "cliente", "assinatura"])
    ap.add_argument("--base", required=True, help="URL base, ex.: http://localhost:8000 ou a URL de produção")
    ap.add_argument("--saida", default="prints", help="pasta dos prints e do estado.json (padrão: prints)")
    ap.add_argument("--senha", default="senha-do-roteiro-e2e", help="senha do dono e do cliente")
    ap.add_argument("--email-dono", default=f"valdir-{agora}@exemplo.com")
    ap.add_argument("--email-cliente", default=f"jorge-{agora}@exemplo.com")
    ap.add_argument("--nome-dono", default="Valdir Rocha")
    ap.add_argument("--empresa", default="Rocha Reformas")
    ap.add_argument("--nome-cliente", default="Jorge Alves")
    ap.add_argument("--obra", default="Reforma da casa do Jorge")
    ap.add_argument("--token", help="token do link do convite (roteiro cliente)")
    ap.add_argument("--email-admin", help="ADMIN_EMAIL da stack (roteiro assinatura)")
    ap.add_argument("--retomar", action="store_true", help="a conta do --email-dono já assinou o Pro")
    ap.add_argument("--senha-admin-arquivo", help="arquivo com a senha do admin, para ela não ir no comando")
    args = ap.parse_args(argv)
    if args.roteiro == "cliente" and not args.token:
        ap.error("o roteiro cliente precisa do --token do link do convite")
    if args.roteiro == "assinatura" and not (args.email_admin and args.senha_admin_arquivo):
        ap.error("o roteiro assinatura precisa de --email-admin e --senha-admin-arquivo")
    return args


def main(argv: list[str]) -> int:
    args = argumentos(argv)
    r = Roteiro(args)
    with sync_playwright() as p:
        try:
            {"dono": dono, "cliente": cliente, "assinatura": assinatura}[args.roteiro](r, p, args)
        except Exception:
            if r.atual is not None:
                r.atual.screenshot(path=str(r.saida / "erro.png"), full_page=True)
                print(f"Falhou em {r.atual.url}; print da tela em {r.saida / 'erro.png'}", file=sys.stderr)
            raise
    if r.erros_no_console:
        print("Erros no console do navegador (o 402 do limite do plano é esperado):")
        for erro in r.erros_no_console:
            print("  ", erro)
    print(f"OK: prints em {r.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
