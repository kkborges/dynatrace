/* dtdash - interface web. Somente JS nativo: nada a instalar, nada a compilar. */

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value === undefined || value === null ? "" : value)
  .replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;" }[c]));

let estado = { tenants: [], templates: [], proposta: null, editando: null, me: null };

async function api(path, options) {
  const config = Object.assign({ headers: {} }, options || {});
  config.headers["X-Requested-With"] = "dtdash";
  if (config.body && typeof config.body === "string") {
    config.headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, config);
  if (response.status === 401) { window.location = "/login"; throw new Error("sessao expirada"); }
  const text = await response.text();
  let data;
  try { data = JSON.parse(text); } catch (e) { data = { raw: text }; }
  if (!response.ok) throw new Error(data.error || ("HTTP " + response.status));
  return data;
}

const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

function show(el, text, ok) {
  el.innerHTML = text;
  el.className = "msg show " + (ok ? "ok" : "err");
}

/* ------------------------------------------------------------- navegacao */
function irPara(view) {
  document.querySelectorAll(".side nav button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) =>
    v.classList.toggle("active", v.id === "view-" + view));
  const carregar = {
    home: carregarHome, clientes: carregarTenants, historico: carregarHistorico,
    biblioteca: carregarTemplates, diagnostico: sincronizarSelectSelftest
  }[view];
  if (carregar) carregar();
}
document.querySelectorAll(".side nav button").forEach((btn) => {
  btn.onclick = () => irPara(btn.dataset.view);
});
document.querySelectorAll("[data-goto]").forEach((btn) => {
  btn.onclick = () => irPara(btn.dataset.goto);
});
$("btnLogout").onclick = async () => { await post("/api/logout"); window.location = "/login"; };

/* ------------------------------------------------------------------ home */
async function carregarHome() {
  const state = await api("/api/state");
  estado.tenants = state.tenants;
  const kpis = [
    ["Clientes", state.clients.length],
    ["Tenants", state.tenants.length],
    ["Dashboards publicados", state.deployments],
    ["Templates", state.templates],
    ["Propostas", state.proposals],
    ["Documentos de conhecimento", state.knowledge.documents]
  ];
  $("kpis").innerHTML = kpis.map(([label, value]) =>
    `<div class="kpi"><div class="n">${esc(value)}</div><div class="l">${esc(label)}</div></div>`
  ).join("");

  const clientes = $("tblClientesHome").querySelector("tbody");
  clientes.innerHTML = state.clients.length ? state.clients.map((c) =>
    `<tr><td><strong>${esc(c.client)}</strong></td><td>${esc((c.tenants || []).join(", "))}</td>
     <td>${esc(c.dashboards)}</td><td>${esc(c.last)}</td></tr>`).join("")
    : '<tr><td colspan="4" class="empty">nenhum dashboard publicado ainda</td></tr>';

  const historico = await api("/api/history");
  const ultimos = $("tblUltimos").querySelector("tbody");
  ultimos.innerHTML = historico.length ? historico.slice(0, 6).map((h) =>
    `<tr><td>${esc(h.when)}</td><td>${esc(h.client)}</td><td>${esc(h.name)}</td>
     <td>${h.url && h.url.startsWith("http")
        ? `<a href="${esc(h.url)}" target="_blank" rel="noopener">abrir</a>` : ""}</td></tr>`
  ).join("") : '<tr><td colspan="4" class="empty">nada publicado ainda</td></tr>';

  $("kbStats").textContent = JSON.stringify(state.knowledge, null, 2);
  preencherSelectTenants();
}

function preencherSelectTenants() {
  const opcoes = estado.tenants.map((t) =>
    `<option value="${esc(t.name)}"${t.default ? " selected" : ""}>${esc(t.name)}` +
    `${t.client && t.client !== t.name ? " - " + esc(t.client) : ""}` +
    `${t.hasCredentials ? "" : " (sem credencial)"}</option>`).join("");
  $("tenant").innerHTML = '<option value="">(offline / sem tenant)</option>' + opcoes;
  $("stTenant").innerHTML = opcoes || '<option value="">(nenhum tenant)</option>';
  const filtro = $("filtroCliente");
  const clientes = [...new Set(estado.tenants.map((t) => t.client).filter(Boolean))];
  filtro.innerHTML = '<option value="">todos os clientes</option>' +
    clientes.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
}

/* -------------------------------------------------------------- clientes */
async function carregarTenants() {
  estado.tenants = await api("/api/tenants");
  const tbody = $("tblTenants").querySelector("tbody");
  tbody.innerHTML = estado.tenants.length ? estado.tenants.map((t) => `
    <tr>
      <td><strong>${esc(t.name)}</strong>${t.default ? ' <span class="tag mut">padrao</span>' : ""}</td>
      <td>${esc(t.client)}</td>
      <td><code>${esc(t.environmentId)}</code></td>
      <td>${t.hasCredentials
        ? `<span class="tag ok">ok</span> ${esc(t.storedSecret ? "gravada" : t.credentialSource)}`
        : `<span class="tag err">ausente</span> ${esc(t.credentialSource)}`}</td>
      <td>${esc(t.dashboards)}${t.lastDeployment ? '<div class="hint">' + esc(t.lastDeployment) + "</div>" : ""}</td>
      <td style="white-space:nowrap">
        <button class="ghost mini" data-edit="${esc(t.name)}">editar</button>
        <button class="ghost mini" data-test="${esc(t.name)}">testar</button>
        <button class="ghost mini danger" data-del="${esc(t.name)}">excluir</button>
      </td>
    </tr>`).join("") : '<tr><td colspan="6" class="empty">nenhum cliente cadastrado</td></tr>';

  tbody.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => editarTenant(b.dataset.edit));
  tbody.querySelectorAll("[data-test]").forEach((b) => b.onclick = () => testarTenant(b.dataset.test));
  tbody.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => excluirTenant(b.dataset.del));
  preencherSelectTenants();
}

$("tAuth").onchange = () => {
  const oauth = $("tAuth").value === "oauth";
  $("authOauth").style.display = oauth ? "" : "none";
  $("authToken").style.display = oauth ? "none" : "";
};

function editarTenant(name) {
  const tenant = estado.tenants.find((t) => t.name === name);
  if (!tenant) return;
  estado.editando = name;
  $("formTenantTitle").textContent = "Editando " + name;
  $("tName").value = tenant.name;
  $("tClient").value = tenant.client || "";
  $("tEnv").value = tenant.environmentId || "";
  $("tUrl").value = tenant.platformUrl || "";
  $("tAuth").value = tenant.authMethod || "platform_token";
  $("tNotes").value = tenant.notes || "";
  $("tTokenEnv").value = tenant.authMethod === "platform_token" ? (tenant.credentialSource || "") : "";
  $("tToken").value = "";
  $("tClientSecret").value = "";
  $("tAuth").onchange();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

$("btnLimparTenant").onclick = () => {
  estado.editando = null;
  $("formTenantTitle").textContent = "Novo cliente";
  ["tName", "tClient", "tEnv", "tUrl", "tNotes", "tTokenEnv", "tToken", "tClientId",
   "tClientSecret", "tUrn"].forEach((id) => { $(id).value = ""; });
  $("msgTenant").className = "msg";
};

$("btnSalvarTenant").onclick = async () => {
  try {
    const payload = {
      name: $("tName").value.trim(),
      client: $("tClient").value.trim(),
      environmentId: $("tEnv").value.trim(),
      platformUrl: $("tUrl").value.trim(),
      authMethod: $("tAuth").value,
      notes: $("tNotes").value,
      tokenEnv: $("tTokenEnv").value.trim(),
      platformToken: $("tToken").value.trim(),
      oauthClientId: $("tClientId").value.trim(),
      oauthClientSecret: $("tClientSecret").value.trim(),
      accountUrn: $("tUrn").value.trim()
    };
    const data = await post("/api/tenants", payload);
    show($("msgTenant"), "cliente <strong>" + esc(data.name) + "</strong> salvo (" +
      esc(data.platformUrl) + ")", true);
    $("btnLimparTenant").onclick();
    carregarTenants();
  } catch (error) { show($("msgTenant"), esc(error.message), false); }
};

async function excluirTenant(name) {
  if (!confirm("Excluir o cadastro de " + name + "? Os dashboards ja publicados nao sao afetados."))
    return;
  try {
    await post("/api/tenants/" + encodeURIComponent(name) + "/delete");
    carregarTenants();
  } catch (error) { show($("msgTenant"), esc(error.message), false); }
}

async function testarTenant(name) {
  const card = $("cardTenantTest");
  card.style.display = "";
  $("tenantTest").innerHTML = "<p class='hint'>testando " + esc(name) + "...</p>";
  try {
    const caps = await post("/api/tenants/" + encodeURIComponent(name) + "/test");
    const linhas = Object.entries(caps.tables || {}).map(([tabela, info]) =>
      `<tr><td><code>${esc(tabela)}</code></td>
       <td><span class="tag ${info.status === "ok" ? "ok" : info.status === "denied" ? "err" : "mut"}">${esc(info.status)}</span></td>
       <td><code>${esc(info.permission || "")}</code></td><td>${esc(info.detail || "")}</td></tr>`).join("");
    $("tenantTest").innerHTML =
      `<p><strong>${esc(name)}</strong> - ${caps.online ? "conectado" : "sem conexao"} &middot; ` +
      `${esc(caps.licenseLabel)}</p>` +
      (caps.missingPermissions && caps.missingPermissions.length
        ? `<p class="tag err">permissoes a conceder: ${esc(caps.missingPermissions.join(", "))}</p>` : "") +
      `<div class="tablewrap"><table><thead><tr><th>Tabela</th><th>Status</th>
       <th>Permissao</th><th>Detalhe</th></tr></thead><tbody>${linhas}</tbody></table></div>` +
      (caps.errors && caps.errors.length ? `<pre>${esc(caps.errors.join("\n"))}</pre>` : "");
  } catch (error) {
    $("tenantTest").innerHTML = `<p class="tag err">${esc(error.message)}</p>`;
  }
}

/* ------------------------------------------------------------- solicitar */
$("btnGerar").onclick = async () => {
  const button = $("btnGerar");
  button.disabled = true;
  show($("msgGerar"), "gerando proposta...", true);
  try {
    const data = await post("/api/plan", {
      description: $("descricao").value,
      tenant: $("tenant").value,
      name: $("nome").value,
      audience: $("audiencia").value,
      segmentMode: $("segmentMode").value,
      onMissing: $("onMissing").value,
      maxTiles: $("maxTiles").value,
      base: $("base").value,
      offline: $("offline").checked,
      validateLive: $("validateLive").checked
    });
    estado.proposta = data.proposalId;
    $("previa").src = data.previewUrl;
    $("abrirPrevia").href = data.previewUrl;
    $("previewMeta").textContent = data.tiles + " tiles";
    $("cardResumo").style.display = "";
    renderResumo(data);
    show($("msgGerar"), "proposta <code>" + esc(data.proposalId) +
      "</code> gerada. Revise a previa ao lado.", true);
  } catch (error) {
    show($("msgGerar"), esc(error.message), false);
  } finally { button.disabled = false; }
};

function renderResumo(data) {
  const report = data.report || {};
  const metricas = data.metricsSummary || {};
  const counts = metricas.counts || {};
  const capacidades = data.capabilities || {};
  const partes = [];
  partes.push(`<p><strong>${esc(data.name)}</strong></p>`);
  partes.push(`<p>${esc(data.tiles)} tiles &middot; audiencia ${esc(data.audience)} &middot; ` +
    `${esc((data.domains || []).join(", "))}</p>`);
  partes.push("<p>" + (data.segments || []).map((s) =>
    `<span class="tag ok">segment: ${esc(s.name)}</span>`).join("") +
    (data.variables || []).map((v) => `<span class="tag">$${esc(v.key)}</span>`).join("") + "</p>");
  partes.push(`<p><span class="tag ${report.errors ? "err" : "ok"}">${esc(report.errors || 0)} erro(s)</span>` +
    `<span class="tag warn">${esc(report.warnings || 0)} aviso(s)</span></p>`);
  if (metricas.available === true) {
    partes.push(`<p class="hint">metricas: ${esc(counts.ok || 0)} ok, ` +
      `${esc(counts.alias || 0)} via chave classica, ${esc(counts.missing || 0)} ausentes</p>`);
  } else if (metricas.reason) {
    partes.push(`<p class="hint">metricas nao verificadas: ${esc(metricas.reason)}</p>`);
  }
  if ((capacidades.missingPermissions || []).length) {
    partes.push(`<p><span class="tag err">permissoes faltando</span> ` +
      `${esc(capacidades.missingPermissions.join(", "))}</p>`);
  }
  if ((data.droppedTiles || []).length) {
    partes.push(`<p class="hint">tiles removidos por metrica inexistente: ` +
      esc(data.droppedTiles.map((t) => t.title).join(", ")) + "</p>");
  }
  if ((data.warnings || []).length) {
    partes.push(`<details><summary class="hint">observacoes (${data.warnings.length})</summary>` +
      `<pre>${esc(data.warnings.join("\n\n"))}</pre></details>`);
  }
  $("resumo").innerHTML = partes.join("");
}

async function aprovar(dryRun) {
  if (!estado.proposta) return;
  if (!dryRun && !confirm("Criar este dashboard no tenant selecionado?")) return;
  show($("msgAprovar"), dryRun ? "simulando..." : "criando no tenant...", true);
  try {
    const data = await post("/api/proposals/" + estado.proposta + "/approve", {
      tenant: $("tenant").value,
      share: $("share").checked,
      noTemplate: !$("saveTemplate").checked,
      dryRun: dryRun
    });
    const link = data.url && data.url.startsWith("http")
      ? ` <a href="${esc(data.url)}" target="_blank" rel="noopener">abrir dashboard</a>` : "";
    show($("msgAprovar"), (dryRun ? "simulacao concluida. " : "dashboard criado. ") +
      "id: <code>" + esc(data.documentId) + "</code>" + link +
      (data.templatePath ? "<br>template: <code>" + esc(data.templatePath) + "</code>" : "") +
      ((data.warnings || []).length ? "<br>avisos: " + esc(data.warnings.join("; ")) : ""), true);
    $("previa").src = "/api/proposals/" + estado.proposta + "/preview?ts=" + Date.now();
  } catch (error) { show($("msgAprovar"), esc(error.message), false); }
}

$("btnAprovar").onclick = () => aprovar(false);
$("btnDryRun").onclick = () => aprovar(true);
$("btnRejeitar").onclick = async () => {
  if (!estado.proposta) return;
  const reason = prompt("Motivo da rejeicao (opcional):") || "";
  await post("/api/proposals/" + estado.proposta + "/reject", { reason });
  show($("msgAprovar"), "proposta rejeitada.", true);
};

/* ------------------------------------------------------------- historico */
async function carregarHistorico() {
  const cliente = $("filtroCliente").value;
  const rows = await api("/api/history" + (cliente ? "?client=" + encodeURIComponent(cliente) : ""));
  const tbody = $("tblHistorico").querySelector("tbody");
  tbody.innerHTML = rows.length ? rows.map((h) => `
    <tr>
      <td>${esc(h.when)}${h.dryRun ? ' <span class="tag mut">simulacao</span>' : ""}</td>
      <td>${esc(h.client)}</td><td>${esc(h.tenant)}</td>
      <td>${esc(h.name)}<div class="hint">${esc((h.domains || []).join(", "))}</div></td>
      <td>${esc(h.tiles)}</td>
      <td>${(h.segments || []).map((s) => `<span class="tag ok">${esc(s.name)}</span>`).join("") || "-"}</td>
      <td>${esc(h.user || "-")}</td>
      <td>${h.url && h.url.startsWith("http")
        ? `<a href="${esc(h.url)}" target="_blank" rel="noopener">dashboard</a>` : ""}
        ${h.proposalId ? ` &middot; <a href="/api/proposals/${esc(h.proposalId)}/preview"
          target="_blank" rel="noopener">previa</a>` : ""}</td>
    </tr>`).join("") : '<tr><td colspan="8" class="empty">nenhum registro</td></tr>';
}
$("filtroCliente").onchange = carregarHistorico;

/* ------------------------------------------------------------ biblioteca */
async function carregarTemplates() {
  estado.templates = await api("/api/templates");
  const tbody = $("tblTemplates").querySelector("tbody");
  tbody.innerHTML = estado.templates.length ? estado.templates.map((t) => `
    <tr><td><span class="tag mut">${esc(t.scope)}</span></td><td>${esc(t.client || "-")}</td>
      <td>${esc(t.name)}</td><td>${esc(t.tiles)}</td>
      <td>${esc((t.domains || []).join(", "))}</td><td><code>${esc(t.ref)}</code></td>
      <td style="white-space:nowrap">
        <button class="ghost mini" data-base="${esc(t.ref)}">usar como base</button>
        <button class="ghost mini" data-json="${esc(t.ref)}">JSON</button></td></tr>`).join("")
    : '<tr><td colspan="7" class="empty">nenhum template</td></tr>';

  tbody.querySelectorAll("[data-base]").forEach((b) => b.onclick = () => {
    irPara("solicitar");
    $("base").value = b.dataset.base;
    $("descricao").focus();
  });
  tbody.querySelectorAll("[data-json]").forEach((b) => b.onclick = async () => {
    const data = await api("/api/template?ref=" + encodeURIComponent(b.dataset.json));
    const janela = window.open("", "_blank");
    janela.document.write("<pre>" + esc(JSON.stringify(data, null, 2)) + "</pre>");
  });

  $("base").innerHTML = '<option value="">nenhum</option>' + estado.templates.map((t) =>
    `<option value="${esc(t.ref)}">${esc(t.name)} [${esc(t.scope)}${t.client ? "/" + esc(t.client) : ""}]</option>`
  ).join("");
}

/* ----------------------------------------------------------- conhecimento */
$("btnSync").onclick = async () => {
  show($("msgKb"), "sincronizando (pode levar alguns minutos)...", true);
  try {
    const data = await post("/api/kb/sync");
    $("kbStats").textContent = JSON.stringify(data.index || data, null, 2);
    show($("msgKb"), "sincronizacao concluida.", true);
  } catch (error) { show($("msgKb"), esc(error.message), false); }
};

$("btnUpload").onclick = async () => {
  const input = $("arquivos");
  if (!input.files.length) { show($("msgKb"), "selecione ao menos um arquivo.", false); return; }
  const form = new FormData();
  for (const file of input.files) form.append("files", file);
  try {
    const data = await api("/api/upload", { method: "POST", body: form });
    $("kbStats").textContent = JSON.stringify(data.knowledge, null, 2);
    show($("msgKb"), "arquivos recebidos: " + data.saved.length, true);
  } catch (error) { show($("msgKb"), esc(error.message), false); }
};

/* ------------------------------------------------------------ diagnostico */
function sincronizarSelectSelftest() { preencherSelectTenants(); }

const ST_TAG = { ok: "ok", warn: "warn", fail: "err", skip: "mut" };

$("btnSelftest").onclick = async () => {
  const tenant = $("stTenant").value;
  if (!tenant) { show($("msgSelftest"), "cadastre um tenant primeiro.", false); return; }
  const write = $("stWrite").checked;
  if (write && !confirm("O modo escrita cria e remove um segment e um dashboard temporarios em " +
      tenant + ". Continuar?")) return;
  const button = $("btnSelftest");
  button.disabled = true;
  show($("msgSelftest"), "executando...", true);
  try {
    const data = await post("/api/selftest",
      { tenant, write, queries: $("stQueries").checked });
    $("tblSelftest").querySelector("tbody").innerHTML = data.checks.map((check) => `
      <tr><td><span class="tag ${ST_TAG[check.status] || "mut"}">${esc(check.status)}</span></td>
        <td>${esc(check.title)}<div class="hint"><code>${esc(check.id)}</code></div></td>
        <td>${esc(check.detail)}${check.hint && check.status !== "ok"
          ? '<div class="hint">-&gt; ' + esc(check.hint) + "</div>" : ""}</td></tr>`).join("");
    show($("msgSelftest"), `${data.counts.ok} ok, ${data.counts.warn} aviso(s), ` +
      `${data.counts.fail} falha(s) em ${data.durationSeconds}s`, data.ok);
  } catch (error) {
    show($("msgSelftest"), esc(error.message), false);
  } finally { button.disabled = false; }
};

/* ----------------------------------------------------------------- inicio */
(async function inicio() {
  try {
    estado.me = await api("/api/me");
    $("whoami").innerHTML = `<strong>${esc(estado.me.fullName || estado.me.user)}</strong>` +
      `<div>${esc(estado.me.role)}</div>`;
  } catch (error) { return; }
  await carregarHome();
  await carregarTemplates();
})();
