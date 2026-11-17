import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as loja  # noqa: E402

TOKEN = {"X-Admin-Token": "teste"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "teste")
    loja.ESTADO["modo"] = "vulneravel"
    loja.PEDIDOS.clear()
    loja.CONTADOR["proximo_id"] = 1
    loja.app.config["TESTING"] = True
    with loja.app.test_client() as c:
        yield c


def comprar(client, preco, produto_id="1", nome="Ana"):
    return client.post(
        "/api/comprar", json={"produto_id": produto_id, "preco": preco, "nome": nome}
    )


def set_modo(client, modo):
    return client.post("/api/admin/modo", json={"modo": modo}, headers=TOKEN)


# 1
def test_status_comeca_vulneravel(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.get_json()["modo"] == "vulneravel"


# 2
def test_lista_tres_produtos(client):
    r = client.get("/api/produtos")
    assert r.status_code == 200
    assert len(r.get_json()) == 3


# 3
def test_vulneravel_compra_normal(client):
    r = comprar(client, "4999.00")
    assert r.status_code == 201
    p = r.get_json()
    assert p["fraude"] is False
    assert p["preco_registrado"] == 4999.0


# 4
def test_vulneravel_ataque(client):
    r = comprar(client, "1")
    assert r.status_code == 201
    p = r.get_json()
    assert p["preco_registrado"] == 1.0
    assert p["fraude"] is True
    assert p["preco_real"] == 4999.0
    assert p["preco_enviado"] == "1"


# 5
def test_vulneravel_preco_negativo(client):
    r = comprar(client, "-100")
    assert r.status_code == 201
    p = r.get_json()
    assert p["preco_registrado"] == -100.0
    assert p["fraude"] is True


def test_vulneravel_aceita_zero_e_centavo(client):
    assert comprar(client, "0").get_json()["fraude"] is True
    assert comprar(client, "0.01").get_json()["preco_registrado"] == 0.01


# 6
@pytest.mark.parametrize("preco", ["abc", "nan", "inf", "-inf", "", None])
def test_vulneravel_preco_invalido(client, preco):
    r = comprar(client, preco)
    assert r.status_code == 400
    assert loja.PEDIDOS == []


def test_vulneravel_sem_campo_preco(client):
    r = client.post("/api/comprar", json={"produto_id": "1"})
    assert r.status_code == 400


# 7
def test_produto_inexistente(client):
    r = comprar(client, "10", produto_id="99")
    assert r.status_code == 400
    assert r.get_json()["erro"] == "Produto inexistente"


# 8
def test_admin_sem_token(client):
    r = client.post("/api/admin/modo", json={"modo": "seguro"})
    assert r.status_code == 401
    assert client.post("/api/admin/limpar").status_code == 401


def test_admin_token_errado(client):
    r = client.post(
        "/api/admin/modo", json={"modo": "seguro"}, headers={"X-Admin-Token": "errado"}
    )
    assert r.status_code == 401
    assert client.get("/api/status").get_json()["modo"] == "vulneravel"


def test_admin_sem_variavel_de_ambiente(client, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN")
    r = set_modo(client, "seguro")
    assert r.status_code == 503
    assert "ADMIN_TOKEN" in r.get_json()["erro"]


# 9
def test_admin_troca_para_seguro(client):
    r = set_modo(client, "seguro")
    assert r.status_code == 200
    assert client.get("/api/status").get_json()["modo"] == "seguro"
    assert set_modo(client, "invalido").status_code == 400


# 10
def test_seguro_ataque_ignorado(client):
    set_modo(client, "seguro")
    r = comprar(client, "1")
    assert r.status_code == 201
    p = r.get_json()
    assert p["preco_registrado"] == 4999.0
    assert p["fraude"] is False
    assert p["preco_enviado"] == "1"
    assert p["modo"] == "seguro"


def test_seguro_ignora_preco_invalido(client):
    set_modo(client, "seguro")
    r = comprar(client, "abc")
    assert r.status_code == 201
    assert r.get_json()["preco_registrado"] == 4999.0


# 11
def test_nome_truncado_e_padrao(client):
    p = comprar(client, "4999", nome="x" * 50).get_json()
    assert p["nome"] == "x" * 30
    p = comprar(client, "4999", nome="   ").get_json()
    assert p["nome"] == "anônimo"
    p = client.post("/api/comprar", json={"produto_id": "1", "preco": "4999"}).get_json()
    assert p["nome"] == "anônimo"


# 12
def test_admin_limpar(client):
    comprar(client, "1")
    comprar(client, "2")
    assert len(client.get("/api/pedidos").get_json()) == 2
    r = client.post("/api/admin/limpar", headers=TOKEN)
    assert r.status_code == 200
    assert client.get("/api/pedidos").get_json() == []


def test_pedidos_mais_recente_primeiro(client):
    comprar(client, "1", nome="primeiro")
    comprar(client, "2", nome="segundo")
    nomes = [p["nome"] for p in client.get("/api/pedidos").get_json()]
    assert nomes == ["segundo", "primeiro"]


# 13
def test_loja_tem_input_preco(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    js = client.get("/app.js").get_data(as_text=True)
    assert 'name="preco"' in html or 'name="preco"' in js


def test_paginas_estaticas(client):
    for pagina in ("/painel.html", "/admin.html", "/style.css"):
        assert client.get(pagina).status_code == 200


# 14
def test_form_urlencoded(client):
    r = client.post(
        "/api/comprar", data={"produto_id": "2", "preco": "10", "nome": "Form"}
    )
    assert r.status_code == 201
    p = r.get_json()
    assert p["preco_registrado"] == 10.0
    assert p["fraude"] is True
    assert p["nome"] == "Form"


def test_limite_de_tamanho(client):
    r = client.post(
        "/api/comprar",
        json={"produto_id": "1", "preco": "1", "nome": "x" * 20000},
    )
    assert r.status_code == 413


def test_limite_de_500_pedidos(client):
    for _ in range(510):
        comprar(client, "1")
    assert len(loja.PEDIDOS) == 500
    assert loja.PEDIDOS[0]["id"] == 11
