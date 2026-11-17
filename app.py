"""Demo A — Design Inseguro (OWASP A04:2021): preço confiado ao cliente.

Loja fictícia para fins acadêmicos. O estado fica em memória: reiniciar zera tudo.
Rode com gunicorn usando 1 worker (ver render.yaml).
"""

import hmac
import math
import os
import threading
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, send_from_directory

try:
    from zoneinfo import ZoneInfo

    FUSO = ZoneInfo("America/Recife")
except Exception:  # Windows sem tzdata: Recife é UTC-3 fixo (sem horário de verão)
    FUSO = timezone(timedelta(hours=-3), "America/Recife")

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024  # 10 KB
app.json.ensure_ascii = False
app.json.sort_keys = False

# ---------------------------------------------------------------------------
# "Banco de dados" em memória
# ---------------------------------------------------------------------------
PRODUTOS = {
    "1": {"id": "1", "nome": "Placa de vídeo RTX", "preco": 4999.00, "emoji": "🎮"},
    "2": {"id": "2", "nome": "Notebook Gamer",     "preco": 3499.00, "emoji": "💻"},
    "3": {"id": "3", "nome": "Fone Bluetooth",     "preco": 299.90,  "emoji": "🎧"},
}
ESTADO = {"modo": "vulneravel"}  # "vulneravel" | "seguro" — começa VULNERÁVEL
PEDIDOS = []                     # mais antigo primeiro; máximo de MAX_PEDIDOS
MAX_PEDIDOS = 500
CONTADOR = {"proximo_id": 1}
LOCK = threading.Lock()


def buscar_preco_no_banco(produto_id):
    return PRODUTOS[produto_id]["preco"]


def registrar_pedido(dados, produto_id, preco):
    if not math.isfinite(preco):
        raise ValueError("preço não finito")
    produto = PRODUTOS[produto_id]
    nome = str(dados.get("nome") or "").strip()[:30] or "anônimo"
    enviado = dados.get("preco")
    with LOCK:
        pedido = {
            "id": CONTADOR["proximo_id"],
            "hora": datetime.now(FUSO).strftime("%H:%M:%S"),
            "nome": nome,
            "produto_id": produto_id,
            "produto": produto["nome"],
            "preco_real": produto["preco"],
            "preco_enviado": None if enviado is None else str(enviado)[:40],
            "preco_registrado": round(preco, 2),
            "modo": ESTADO["modo"],
            "fraude": abs(preco - produto["preco"]) > 0.001,
        }
        CONTADOR["proximo_id"] += 1
        PEDIDOS.append(pedido)
        del PEDIDOS[:-MAX_PEDIDOS]
    print(
        f"[{pedido['hora']}] {nome} | {produto['nome']} | real {produto['preco']:.2f}"
        f" | registrado {pedido['preco_registrado']:.2f} | {pedido['modo']}",
        flush=True,
    )
    return pedido


# ===========================================================================
# O CORAÇÃO DA DEMO
# ===========================================================================

# VULNERAVEL: confia no que o cliente envia
def comprar_vulneravel(dados):
    produto_id = dados["produto_id"]
    preco = float(dados["preco"])                # <- vem do navegador
    return registrar_pedido(dados, produto_id, preco)

# CORRIGIDO: o servidor e a fonte da verdade
def comprar_seguro(dados):
    produto_id = dados["produto_id"]
    preco = buscar_preco_no_banco(produto_id)    # <- regra no servidor
    return registrar_pedido(dados, produto_id, preco)

# ===========================================================================


def erro(mensagem, status):
    return jsonify({"erro": mensagem}), status


def ler_dados():
    if request.is_json:
        dados = request.get_json(silent=True)
    else:
        dados = request.form.to_dict()
    if not isinstance(dados, dict):
        return None
    if "produto_id" in dados:
        dados["produto_id"] = str(dados["produto_id"])
    return dados


@app.get("/")
def loja():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/status")
def status():
    return jsonify({"modo": ESTADO["modo"]})


@app.get("/api/produtos")
def produtos():
    return jsonify(list(PRODUTOS.values()))


@app.post("/api/comprar")
def comprar():
    dados = ler_dados()
    if dados is None:
        return erro("Corpo inválido", 400)
    if dados.get("produto_id") not in PRODUTOS:
        return erro("Produto inexistente", 400)
    funcao = comprar_seguro if ESTADO["modo"] == "seguro" else comprar_vulneravel
    try:
        pedido = funcao(dados)
    except (KeyError, ValueError, TypeError, OverflowError):
        return erro("Preço inválido", 400)
    return jsonify(pedido), 201


@app.get("/api/pedidos")
def pedidos():
    with LOCK:
        return jsonify(list(reversed(PEDIDOS)))


def checar_admin():
    """Retorna None se autorizado, ou a resposta de erro."""
    esperado = os.environ.get("ADMIN_TOKEN", "")
    if not esperado:
        return erro("ADMIN_TOKEN não configurado no servidor", 503)
    recebido = request.headers.get("X-Admin-Token", "")
    if not hmac.compare_digest(recebido.encode(), esperado.encode()):
        return erro("Token inválido", 401)
    return None


@app.post("/api/admin/modo")
def admin_modo():
    negado = checar_admin()
    if negado:
        return negado
    dados = request.get_json(silent=True) or {}
    modo = dados.get("modo")
    if modo not in ("vulneravel", "seguro"):
        return erro("Modo deve ser 'vulneravel' ou 'seguro'", 400)
    ESTADO["modo"] = modo
    print(f"[admin] modo -> {modo}", flush=True)
    return jsonify({"modo": modo})


@app.post("/api/admin/limpar")
def admin_limpar():
    negado = checar_admin()
    if negado:
        return negado
    with LOCK:
        PEDIDOS.clear()
        CONTADOR["proximo_id"] = 1
    print("[admin] pedidos limpos", flush=True)
    return jsonify({"ok": True, "pedidos": 0})


@app.errorhandler(413)
def muito_grande(_e):
    return erro("Requisição muito grande (máx. 10 KB)", 413)


@app.errorhandler(404)
def nao_encontrado(_e):
    if request.path.startswith("/api/"):
        return erro("Rota não encontrada", 404)
    return send_from_directory(app.static_folder, "index.html"), 404


@app.after_request
def cabecalhos(resp):
    resp.headers["X-Robots-Tag"] = "noindex"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
