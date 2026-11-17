// Helpers compartilhados. Todo texto vindo do servidor entra com textContent.
const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

function brl(valor) {
  const n = Number(valor);
  return Number.isFinite(n) ? BRL.format(n) : String(valor);
}

async function api(caminho, opcoes = {}) {
  const resp = await fetch(caminho, { cache: 'no-store', ...opcoes });
  let corpo = null;
  try { corpo = await resp.json(); } catch (_) { /* resposta sem JSON */ }
  return { ok: resp.ok, status: resp.status, corpo };
}

function pintarSelo(el, modo) {
  el.dataset.modo = modo;
  el.textContent = modo === 'seguro' ? 'Modo seguro' : 'Modo vulnerável';
}

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined && texto !== null) e.textContent = texto;
  return e;
}
