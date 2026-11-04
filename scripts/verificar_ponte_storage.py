"""Confere, numa stack de pé (Garage de verdade), que a ponte /storage só deixa passar o que a
API assinou, e que a assinatura prende a URL à chave da empresa.

Uso: python scripts/verificar_ponte_storage.py [http://localhost:8000]
(o CI roda depois de subir o docker-compose.ci.yml)

1. Cria duas empresas (A e B), cada uma com uma obra e um diário.
2. A pede uma URL de envio; trocar a empresa, a obra ou o diário da chave pela B → 403 do Garage.
3. O envio pela URL original funciona, e a confirmação grava a foto.
4. A URL de leitura da foto de A, com a chave trocada pela de uma foto de B → 403.
5. Sem assinatura → 403; fora de empresas/ → 404.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
JPEG = b"\xff\xd8\xff\xe0" + b"nivelo" * 200
falhas: list[str] = []


def conferir(descricao: str, obtido: int, esperado: int) -> None:
    ok = obtido == esperado
    print(f"  [{'ok' if ok else 'FALHOU'}] {descricao}: {obtido} (esperado {esperado})")
    if not ok:
        falhas.append(descricao)


def empresa(c: httpx.Client, nome: str) -> dict[str, Any]:
    email = f"{nome.lower().replace(' ', '-')}-{time.time_ns()}@exemplo.com"
    cad = c.post(
        "/api/auth/cadastro", json={"nome": nome, "email": email, "senha": "verificacao-123", "empresa_nome": nome}
    )
    cad.raise_for_status()
    login = c.post("/api/auth/login", data={"username": email, "password": "verificacao-123"})
    login.raise_for_status()
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    obra = c.post(
        "/api/obras",
        headers=h,
        json={
            "nome": f"Obra {nome}",
            "endereco": {"logradouro": "Rua 1", "cidade": "Marília", "uf": "SP"},
            "cliente_nome": "Cliente",
            "data_inicio": "2026-01-01",
            "previsao_termino": "2026-12-31",
        },
    )
    obra.raise_for_status()
    diario = c.post(
        f"/api/obras/{obra.json()['id']}/diarios", headers=h, json={"data": "2026-01-02", "atividades": "x"}
    )
    diario.raise_for_status()
    return {
        "token": token,
        "empresa": cad.json()["empresa"]["id"],
        "obra": obra.json()["id"],
        "diario": diario.json()["id"],
    }


def pedir_envio(c: httpx.Client, e: dict[str, Any]) -> dict[str, Any]:
    r = c.post(
        f"/api/diarios/{e['diario']}/fotos/upload-url",
        headers={"Authorization": f"Bearer {e['token']}"},
        json={"content_type": "image/jpeg", "tamanho_bytes": len(JPEG)},
    )
    r.raise_for_status()
    return r.json()


def enviar_e_confirmar(c: httpx.Client, e: dict[str, Any]) -> dict[str, Any]:
    p = pedir_envio(c, e)
    httpx.put(BASE + p["url"], content=JPEG, headers=p["headers"]).raise_for_status()
    r = c.post(
        f"/api/diarios/{e['diario']}/fotos",
        headers={"Authorization": f"Bearer {e['token']}"},
        json={"object_key": p["object_key"]},
    )
    r.raise_for_status()
    leitura = c.get(f"/api/fotos/{r.json()['id']}/url", headers={"Authorization": f"Bearer {e['token']}"}).json()
    return {"object_key": p["object_key"], "url": leitura["url"]}


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=20)
    a, b = empresa(c, "Empresa A"), empresa(c, "Empresa B")
    print("Envio (PUT) com URL assinada para a empresa A")
    p = pedir_envio(c, a)
    for campo, rotulo in (
        ("empresa", "a empresa trocada pela B"),
        ("obra", "a obra trocada pela de B"),
        ("diario", "o diário trocado pelo de B"),
    ):
        trocada = p["url"].replace(a[campo], b[campo], 1)
        assert trocada != p["url"]
        r = httpx.put(BASE + trocada, content=JPEG, headers=p["headers"])
        conferir(f"chave com {rotulo}", r.status_code, 403)
    r = httpx.put(BASE + p["url"], content=JPEG, headers={"Content-Type": "image/png"})
    conferir("Content-Type diferente do assinado", r.status_code, 403)
    sem_assinatura = p["url"].split("?", 1)[0]
    conferir("sem assinatura", httpx.put(BASE + sem_assinatura, content=JPEG, headers=p["headers"]).status_code, 403)
    fora = p["url"].replace("/empresas/", "/avatares/", 1)
    conferir("fora de empresas/", httpx.put(BASE + fora, content=JPEG, headers=p["headers"]).status_code, 404)
    conferir("URL original", httpx.put(BASE + p["url"], content=JPEG, headers=p["headers"]).status_code, 200)

    print("Leitura (GET) com URL assinada para a foto de A")
    foto_a, foto_b = enviar_e_confirmar(c, a), enviar_e_confirmar(c, b)
    trocada = foto_a["url"].replace(foto_a["object_key"], foto_b["object_key"], 1)
    conferir("chave trocada pela da foto da empresa B", httpx.get(BASE + trocada).status_code, 403)
    conferir("URL original", httpx.get(BASE + foto_a["url"]).status_code, 200)

    if falhas:
        print(f"\nFALHOU: {len(falhas)} verificação(ões)")
        return 1
    print("\nOK: a ponte /storage só repassa o que a API assinou para a chave certa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
