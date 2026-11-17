# Demo A: preço confiado ao cliente

Demonstração prática de **Design Inseguro (OWASP A04:2021)** para o seminário de Segurança de Sistemas (UPE).
Uma mini loja aceita o preço que vem do navegador: não é bug de implementação, é o requisito que está errado.
A correção não é um filtro no campo, e sim mudar **quem define o preço**: o servidor busca o valor no banco.

> **Aviso:** loja fictícia, uso exclusivamente acadêmico. Nenhuma compra é real.

## Páginas

| Rota | Para quê |
|---|---|
| `/` | Loja (o alvo do ataque) |
| `/painel.html` | Pedidos ao vivo, com fraudes em destaque (projetor) |
| `/admin.html` | Alterna modo vulnerável ⇄ seguro e limpa pedidos (exige token) |

## O trecho que importa (`app.py`)

```python
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
```

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
ADMIN_TOKEN=teste python app.py  # http://localhost:5000
pytest -q
```

Em produção (Render) o comando é `gunicorn app:app --workers 1 --threads 8`. **Use sempre 1 worker:** pedidos e modo ficam na memória do processo.

## Como atacar

1. **DevTools → Elements:** F12, inspecione o card do produto, ache
   `<input type="hidden" name="preco" value="4999.00">`, troque o `value` para `1` e clique em **Comprar**.
2. **DevTools → Network:** faça uma compra normal, clique com o botão direito na requisição `comprar`,
   **Copy → Copy as cURL**, edite o `"preco"` no comando e rode no terminal.
3. **Console do navegador:**
   ```js
   fetch('/api/comprar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({produto_id:'1',preco:'0.01',nome:'hacker'})}).then(r=>r.json()).then(console.log)
   ```

No modo vulnerável o servidor aceita qualquer número finito (inclusive `0` e negativos). No modo seguro o campo `preco` é ignorado e só aparece no painel, riscado.

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/status` | `{"modo": "vulneravel"}` (health check) |
| GET | `/api/produtos` | Produtos com o preço real |
| POST | `/api/comprar` | JSON ou form: `{"produto_id": "1", "preco": "4999.00", "nome": "Ana"}` |
| GET | `/api/pedidos` | Pedidos, do mais recente para o mais antigo |
| POST | `/api/admin/modo` | `{"modo": "seguro"}` ou `{"modo": "vulneravel"}`, header `X-Admin-Token` |
| POST | `/api/admin/limpar` | Zera os pedidos, header `X-Admin-Token` |

## Roteiro da demonstração

1. **Projetor:** abrir `/painel.html`. Em outra aba, a loja e o QR code (`/qr.png`).
2. **Compra normal:** comprar a placa de vídeo por R$ 4.999 e ver a linha OK no painel.
3. **Ataque:** F12 → Elements → `<input type="hidden" name="preco" value="4999.00">` → trocar para `1` → Comprar.
   Aparece "aprovado por R$ 1,00 😈" e a linha FRAUDE no painel.
4. **Turma ataca:** "escaneiem o QR e tentem comprar pelo menor preço possível". O contador de prejuízo sobe.
5. **Explicar:** não há bug; o código faz o que foi especificado. O requisito deixou o cliente definir o preço.
   STRIDE: Tampering → integridade. Princípio quebrado: não confiar no cliente.
6. **Correção:** em `/admin.html`, clicar em "Aplicar a correção". Mostrar `comprar_seguro` no código.
7. **Turma ataca de novo:** todos recebem 🛡️ e o painel só mostra OK.
   *"A correção não foi um filtro no campo: mudou quem define o preço."*

## Deploy (Render)

`render.yaml` é um Blueprint: **New → Blueprint**, selecione este repositório e informe o `ADMIN_TOKEN` quando pedido.
O plano free dorme após ~15 min sem acesso; abra a loja e o painel uns 5 minutos antes de apresentar.
Reiniciar ou fazer redeploy zera os pedidos e volta ao modo vulnerável.

Smoke test da URL publicada:

```bash
bash scripts/smoke_test.sh https://SEU-APP.onrender.com SEU_TOKEN
```
