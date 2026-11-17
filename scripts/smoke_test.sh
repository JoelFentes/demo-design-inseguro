#!/usr/bin/env bash
# Smoke test da demo publicada.
# Uso: bash scripts/smoke_test.sh https://demo-design-inseguro-xxxx.onrender.com [ADMIN_TOKEN]
set -u

BASE="${1:?Uso: $0 URL_BASE [ADMIN_TOKEN]}"
BASE="${BASE%/}"
TOKEN="${2:-}"
FALHAS=0

ok()   { echo "  [OK]    $1"; }
falha() { echo "  [FALHA] $1"; FALHAS=$((FALHAS + 1)); }

comprar() {
  curl -s --max-time 90 -X POST "$BASE/api/comprar" \
    -H "Content-Type: application/json" \
    -d "{\"produto_id\":\"1\",\"preco\":\"$1\",\"nome\":\"smoke-test\"}"
}

admin() {
  local CORPO="{}"; [ $# -ge 2 ] && CORPO="$2"
  curl -s --max-time 30 -o /dev/null -w "%{http_code}" -X POST "$BASE/api/admin/$1" \
    -H "Content-Type: application/json" -H "X-Admin-Token: $TOKEN" -d "$CORPO"
}

echo "Smoke test em $BASE"

echo "1. GET /api/status"
CODE=$(curl -s --max-time 90 -o /dev/null -w "%{http_code}" "$BASE/api/status")
[ "$CODE" = "200" ] && ok "status 200" || falha "status retornou $CODE"
MODO_INICIAL=$(curl -s --max-time 30 "$BASE/api/status")
echo "     $MODO_INICIAL"

echo "2. GET / contém o input hidden de preço"
HTML=$(curl -s --max-time 30 "$BASE/")
echo "$HTML" | grep -q 'name="preco"' && ok 'HTML contém name="preco"' || falha 'name="preco" não encontrado'

if [ -n "$TOKEN" ]; then
  echo "   (garantindo modo vulnerável antes do ataque)"
  [ "$(admin modo '{"modo":"vulneravel"}')" = "200" ] && ok "modo vulnerável" || falha "não conseguiu definir modo vulnerável (token?)"
fi

echo "3. Ataque com preço 0.01 (modo vulnerável)"
R=$(comprar 0.01)
echo "     $R"
echo "$R" | grep -Eq '"fraude": ?true' && ok "fraude aceita" || falha "esperava fraude: true"

if [ -n "$TOKEN" ]; then
  echo "4. Correção: modo seguro + novo ataque"
  [ "$(admin modo '{"modo":"seguro"}')" = "200" ] && ok "modo seguro aplicado" || falha "falhou ao aplicar modo seguro"
  R=$(comprar 0.01)
  echo "     $R"
  echo "$R" | grep -Eq '"fraude": ?false' && ok "ataque bloqueado" || falha "esperava fraude: false"
  echo "$R" | grep -Eq '"preco_registrado": ?4999' && ok "preço do banco (4999)" || falha "preço registrado incorreto"

  echo "5. Limpeza: volta ao modo vulnerável e zera pedidos"
  [ "$(admin modo '{"modo":"vulneravel"}')" = "200" ] && ok "modo vulnerável" || falha "falhou ao voltar ao modo vulnerável"
  [ "$(admin limpar)" = "200" ] && ok "pedidos limpos" || falha "falhou ao limpar"
  echo "     $(curl -s --max-time 30 "$BASE/api/status") | pedidos: $(curl -s --max-time 30 "$BASE/api/pedidos")"
else
  echo "4. (sem token: pulando teste do modo seguro e limpeza)"
fi

echo
if [ "$FALHAS" -eq 0 ]; then
  echo "RESULTADO: tudo OK"
else
  echo "RESULTADO: $FALHAS falha(s)"
  exit 1
fi
