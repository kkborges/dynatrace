"""Previa do dashboard para analise e aprovacao do solicitante."""

import html
import json
import re
import time

from .builder import GRID_COLUMNS, build_dashboard

VIZ_LABEL = {
    "lineChart": "linha", "areaChart": "area", "barChart": "barras (tempo)",
    "bandChart": "banda", "categoricalBarChart": "barras", "pieChart": "pizza",
    "donutChart": "rosca", "singleValue": "valor unico", "meterBar": "medidor",
    "gauge": "gauge", "table": "tabela", "raw": "bruto", "recordList": "registros",
    "histogram": "histograma", "honeycomb": "colmeia", "choroplethMap": "mapa",
    "dotMap": "mapa de pontos", "heatmap": "heatmap", "scatterplot": "dispersao",
}

_SPARK = "M0,26 L14,18 L28,22 L42,10 L56,15 L70,6 L84,12 L98,4"


def _esc(value):
    return html.escape(str(value if value is not None else ""))


def render_markdown(text):
    """Markdown minimo (titulos, negrito, italico, listas) para a previa."""

    out = []
    in_list = False
    for raw in (text or "").splitlines():
        line = _esc(raw.rstrip())
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append("<li>%s</li>" % _inline_md(stripped[2:]))
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if not stripped:
            out.append("<br>")
        elif stripped.startswith("### "):
            out.append("<h3>%s</h3>" % _inline_md(stripped[4:]))
        elif stripped.startswith("## "):
            out.append("<h2 class=\"mdh\">%s</h2>" % _inline_md(stripped[3:]))
        elif stripped.startswith("# "):
            out.append("<h1 class=\"mdh\">%s</h1>" % _inline_md(stripped[2:]))
        else:
            out.append("<p>%s</p>" % _inline_md(stripped))
    if in_list:
        out.append("</ul>")
    return "".join(out)


def _inline_md(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _viz_sketch(viz):
    if viz in ("lineChart", "areaChart", "bandChart"):
        fill = ' fill="rgba(88,143,255,.18)"' if viz != "lineChart" else ' fill="none"'
        return ('<svg viewBox="0 0 100 32" preserveAspectRatio="none" class="sk">'
                '<path d="%s"%s stroke="#588fff" stroke-width="2"/></svg>' % (_SPARK, fill))
    if viz in ("barChart", "categoricalBarChart", "histogram"):
        bars = ""
        for index, height in enumerate([10, 18, 26, 14, 22, 8, 16]):
            bars += '<rect x="%d" y="%d" width="9" height="%d" fill="#588fff"/>' % (
                index * 14 + 2, 32 - height, height)
        return '<svg viewBox="0 0 100 32" class="sk">%s</svg>' % bars
    if viz in ("pieChart", "donutChart"):
        inner = '<circle cx="16" cy="16" r="7" fill="#fff"/>' if viz == "donutChart" else ""
        return ('<svg viewBox="0 0 100 32" class="sk">'
                '<circle cx="16" cy="16" r="14" fill="#588fff"/>'
                '<path d="M16,16 L16,2 A14,14 0 0,1 29,20 Z" fill="#7ad1c4"/>%s</svg>' % inner)
    if viz in ("singleValue", "meterBar", "gauge"):
        return '<div class="sk big">42</div>'
    if viz in ("table", "raw", "recordList"):
        rows = "".join(
            '<div class="row"><span></span><span></span><span></span></div>' for _ in range(4)
        )
        return '<div class="sk tbl">%s</div>' % rows
    if viz in ("choroplethMap", "dotMap", "bubbleMap", "connectionMap"):
        return ('<svg viewBox="0 0 100 32" class="sk">'
                '<ellipse cx="50" cy="16" rx="46" ry="13" fill="#dfe7f5"/>'
                '<circle cx="35" cy="14" r="4" fill="#588fff"/>'
                '<circle cx="62" cy="19" r="6" fill="#7ad1c4"/></svg>')
    return '<div class="sk"></div>'


def render_html(spec, report=None, document=None, deployment=None):
    document = document or build_dashboard(spec)
    layouts = document["content"]["layouts"]
    tiles_by_id = {t.tile_id: t for t in spec.tiles}
    coverage = spec.coverage()

    ordered = sorted(
        layouts.items(), key=lambda kv: (int(kv[1]["y"]), int(kv[1]["x"]), kv[0])
    )

    cards = []
    for tile_id, layout in ordered:
        tile = tiles_by_id.get(tile_id)
        if tile is None:
            continue
        span = int(layout["w"])
        if tile.kind == "markdown":
            cards.append(
                '<div class="tile md" style="grid-column: span %d">%s</div>'
                % (span, render_markdown(tile.markdown))
            )
            continue
        answers = ", ".join(tile.answers) or "-"
        notes = ""
        if tile.availability == "missing":
            notes = ('<div class="warn">metrica inexistente no tenant: %s</div>'
                     % _esc(", ".join(tile.unverified_metrics)))
        elif tile.unverified_metrics:
            notes = ('<div class="warn">metricas a verificar: %s</div>'
                     % _esc(", ".join(tile.unverified_metrics)))
        for resolution in tile.metric_resolutions or []:
            if resolution.get("status") == "alias":
                notes += ('<div class="meta">chave classica: %s -> %s</div>'
                          % (_esc(resolution.get("key")), _esc(resolution.get("resolved"))))
        segments = ""
        if tile.segments:
            segments = '<div class="chiprow">%s</div>' % "".join(
                '<span class="chip seg">segment: %s</span>' % _esc(_segment_name(spec, key))
                for key in tile.segments
            )
        cards.append(
            '<div class="tile" style="grid-column: span %d">'
            '<div class="thead"><strong>%s</strong>'
            '<span class="chip">%s</span></div>'
            '<div class="tdesc">%s</div>%s%s%s'
            '<details><summary>DQL</summary><pre>%s</pre></details>'
            '<div class="meta">requisitos: %s &middot; %dx%d</div>'
            "</div>"
            % (
                span,
                _esc(tile.title),
                _esc(VIZ_LABEL.get(tile.visualization, tile.visualization)),
                _esc(tile.description),
                _viz_sketch(tile.visualization),
                segments,
                notes,
                _esc(tile.query),
                _esc(answers),
                span,
                int(layout["h"]),
            )
        )

    requirement_rows = []
    for requirement in spec.requirements:
        tiles = coverage.get(requirement.req_id) or []
        titles = ", ".join(
            _esc(tiles_by_id[t].title) for t in tiles if t in tiles_by_id
        ) or '<span class="warn">sem tile dedicado</span>'
        requirement_rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (_esc(requirement.req_id), _esc(requirement.text), titles)
        )

    segment_rows = []
    for segment in spec.segments:
        filters = "<br>".join(
            "<code>%s</code>: %s" % (_esc(i["dataObject"]), _esc(i["filter"]))
            for i in segment.includes
        )
        status = "verificado no tenant" if segment.verified else "campos nao verificados"
        segment_rows.append(
            "<tr><td>%s%s</td><td>%s</td><td>%s</td></tr>"
            % (
                _esc(segment.name),
                '<div class="meta">%s</div>' % _esc(segment.uid) if segment.uid else "",
                filters,
                _esc(status),
            )
        )

    variable_rows = [
        "<tr><td>$%s</td><td>%s</td><td>%s</td><td><code>%s</code></td></tr>"
        % (
            _esc(v.key), _esc(v.var_type), "multipla" if v.multiple else "unica",
            _esc(v.input or v.default_value),
        )
        for v in spec.variables
    ]

    finding_rows = []
    if report is not None:
        for finding in report.findings:
            finding_rows.append(
                '<tr class="%s"><td>%s</td><td>%s</td><td>%s</td></tr>'
                % (_esc(finding.level), _esc(finding.level), _esc(finding.tile or "-"),
                   _esc(finding.message))
            )

    query_rows = []
    if report is not None:
        for entry in report.query_results or []:
            query_rows.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (
                    _esc(entry.get("tile")), _esc(entry.get("title")),
                    _esc(entry.get("status")),
                    _esc(entry.get("message") or entry.get("records", "")),
                )
            )

    knowledge_rows = [
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_esc(k.get("source")), _esc(k.get("title")), _esc(k.get("path")))
        for k in spec.knowledge_sources
    ]

    warnings_html = "".join("<li>%s</li>" % _esc(w) for w in spec.warnings)
    deployment_html = ""
    if deployment:
        deployment_html = (
            '<section><h2>Publicacao</h2><table>%s</table></section>'
            % "".join(
                "<tr><td>%s</td><td>%s</td></tr>" % (_esc(k), _esc(v))
                for k, v in deployment.items()
            )
        )

    capabilities = spec.capabilities or {}
    denied = capabilities.get("deniedTables") or []
    permission_rows = []
    for table, info in sorted((capabilities.get("tables") or {}).items()):
        status = info.get("status", "?")
        permission_rows.append(
            '<tr class="%s"><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % ("warning" if status == "denied" else "", _esc(table), _esc(status),
               _esc(info.get("permission", "")), _esc(info.get("detail", "")))
        )

    summary = spec.metrics_summary or {}
    counts = summary.get("counts") or {}
    if summary.get("available") is True:
        metrics_line = ("indice do tenant lido (%s chaves): %s ok, %s com chave classica, "
                        "%s ausentes" % (summary.get("indexSize", "?"), counts.get("ok", 0),
                                         counts.get("alias", 0), counts.get("missing", 0)))
    elif summary:
        metrics_line = "nao verificado: %s" % (summary.get("reason") or "-")
    else:
        metrics_line = "sem metricas no dashboard"

    dropped_rows = [
        "<tr><td>%s</td><td>%s</td></tr>"
        % (_esc(entry.get("title")), _esc(", ".join(entry.get("metrics") or [])))
        for entry in spec.dropped_tiles or []
    ]

    return TEMPLATE % {
        "title": _esc(spec.name),
        "description": _esc(spec.description),
        "generated": time.strftime("%d/%m/%Y %H:%M:%S"),
        "tenant": _esc(spec.tenant or "(nao informado)"),
        "client": _esc(spec.client_name or "-"),
        "audience": _esc(spec.audience),
        "license": _esc((spec.capabilities or {}).get("licenseLabel", "nao verificado")),
        "domains": _esc(", ".join(spec.domains)),
        "tilecount": len(spec.data_tiles()),
        "columns": GRID_COLUMNS,
        "cards": "".join(cards),
        "requirements": "".join(requirement_rows) or '<tr><td colspan="3">-</td></tr>',
        "segments": "".join(segment_rows) or '<tr><td colspan="3">nenhum segment</td></tr>',
        "variables": "".join(variable_rows) or '<tr><td colspan="4">nenhuma variavel</td></tr>',
        "findings": "".join(finding_rows) or '<tr><td colspan="3">sem apontamentos</td></tr>',
        "queries": "".join(query_rows) or '<tr><td colspan="4">validacao ao vivo nao executada</td></tr>',
        "knowledge": "".join(knowledge_rows) or '<tr><td colspan="3">-</td></tr>',
        "warnings": warnings_html or "<li>-</li>",
        "deployment": deployment_html,
        "metricsline": _esc(metrics_line),
        "permissions": "".join(permission_rows) or '<tr><td colspan="4">nao sondado</td></tr>',
        "dropped": "".join(dropped_rows) or '<tr><td colspan="2">nenhum</td></tr>',
        "deniedbanner": ('<p class="warn">Tabelas sem permissao de leitura: %s. Os tiles que '
                         'dependem delas ficarao vazios ate que a permissao seja concedida.</p>'
                         % _esc(", ".join(denied))) if denied else "",
        "json": _esc(json.dumps(document, ensure_ascii=False, indent=2)),
    }


def _segment_name(spec, key):
    for segment in spec.segments:
        if segment.key == key:
            return segment.name
    return key


def render_text(spec, report=None):
    """Previa compacta para terminal."""

    lines = []
    lines.append("=" * 78)
    lines.append("DASHBOARD: %s" % spec.name)
    lines.append("=" * 78)
    lines.append("Tenant .....: %s" % (spec.tenant or "(nao informado)"))
    lines.append("Cliente ....: %s" % (spec.client_name or "-"))
    lines.append("Audiencia ..: %s" % spec.audience)
    lines.append("Dominios ...: %s" % ", ".join(spec.domains))
    lines.append("Licenca ....: %s" % (spec.capabilities or {}).get("licenseLabel", "-"))
    lines.append("")
    lines.append("REQUISITOS -> TILES")
    coverage = spec.coverage()
    titles = {t.tile_id: t.title for t in spec.tiles}
    for requirement in spec.requirements:
        covered = coverage.get(requirement.req_id) or []
        names = ", ".join(titles.get(t, t) for t in covered) or "!! sem tile dedicado"
        lines.append("  [%s] %s" % (requirement.req_id, requirement.text[:70]))
        lines.append("        -> %s" % names[:150])
    lines.append("")
    if spec.segments:
        lines.append("SEGMENTS A CRIAR")
        for segment in spec.segments:
            lines.append("  - %s (%s = %s)%s"
                         % (segment.name, segment.dimension, segment.value,
                            "" if segment.verified else "  [campos nao verificados]"))
        lines.append("")
    if spec.variables:
        lines.append("VARIAVEIS")
        for variable in spec.variables:
            lines.append("  - $%s (%s)" % (variable.key, variable.var_type))
        lines.append("")
    lines.append("TILES (%d de dados)" % len(spec.data_tiles()))
    for tile in spec.tiles:
        if tile.kind == "markdown":
            lines.append("  # %s" % (tile.markdown or "").splitlines()[0][:70])
            continue
        lines.append("  - [%s] %s" % (tile.visualization, tile.title))
        first_line = (tile.query or "").splitlines()[0] if tile.query else ""
        lines.append("      %s" % first_line[:100])
    capabilities = spec.capabilities or {}
    if capabilities.get("deniedTables"):
        lines.append("")
        lines.append("PERMISSOES FALTANDO")
        lines.append("  tabelas negadas: %s" % ", ".join(capabilities["deniedTables"]))
        lines.append("  conceda: %s" % ", ".join(capabilities.get("missingPermissions") or []))
    summary = spec.metrics_summary or {}
    if summary:
        counts = summary.get("counts") or {}
        lines.append("")
        if summary.get("available") is True:
            lines.append("METRICAS: %d ok, %d com chave classica, %d ausentes (indice com %s chaves)"
                         % (counts.get("ok", 0), counts.get("alias", 0),
                            counts.get("missing", 0), summary.get("indexSize", "?")))
        else:
            lines.append("METRICAS: nao verificadas (%s)" % (summary.get("reason") or "-"))
    if spec.dropped_tiles:
        lines.append("TILES REMOVIDOS (metrica inexistente):")
        for entry in spec.dropped_tiles:
            lines.append("  - %s [%s]" % (entry.get("title"),
                                          ", ".join(entry.get("metrics") or [])))
    if report is not None:
        lines.append("")
        lines.append("VALIDACAO: %d erro(s), %d aviso(s)"
                     % (len(report.errors), len(report.warnings)))
        for finding in report.findings[:20]:
            lines.append("  %-7s %-4s %s" % (finding.level, finding.tile or "-",
                                             finding.message[:100]))
        if len(report.findings) > 20:
            lines.append("  ... e mais %d apontamento(s) - veja a previa HTML"
                         % (len(report.findings) - 20))
    if spec.warnings:
        lines.append("")
        lines.append("OBSERVACOES")
        for warning in spec.warnings:
            lines.append("  * %s" % warning[:150])
    return "\n".join(lines)


TEMPLATE = """<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Previa - %(title)s</title>
<style>
:root{color-scheme:light dark;--bg:#f6f7fb;--fg:#131a24;--card:#fff;--line:#dbe1ec;
--muted:#5d6b80;--accent:#588fff;--warn:#b8730d;--err:#c62239;--ok:#2f6862}
@media (prefers-color-scheme:dark){:root{--bg:#12151c;--fg:#e8ecf3;--card:#1a1f29;
--line:#2b3342;--muted:#98a3b6}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{background:linear-gradient(120deg,#1f2a44,#2c4a7a);color:#fff;padding:22px 26px}
header h1{margin:0 0 6px;font-size:22px}
header p{margin:0;opacity:.85}
.badges{margin-top:12px;display:flex;flex-wrap:wrap;gap:8px}
.badges span{background:rgba(255,255,255,.16);padding:3px 10px;border-radius:999px;font-size:12px}
main{padding:22px 26px;max-width:1400px;margin:0 auto}
section{margin-bottom:28px}
h2{font-size:16px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
border-bottom:1px solid var(--line);padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(%(columns)d,1fr);gap:10px}
.tile{grid-column:span 12;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:12px;min-height:96px}
.tile.md{background:transparent;border:none;padding:2px;min-height:0}
.tile.md p{margin:2px 0}
.tile.md ul{margin:4px 0 4px 4px}
.tile.md h1.mdh{font-size:19px;margin:2px 0 6px}
.tile.md h2.mdh{font-size:14px;margin:10px 0 2px;text-transform:uppercase;
letter-spacing:.06em;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:4px}
.tile.md h3{font-size:13px;margin:6px 0 2px}
.tile.md br{line-height:.5}
.thead{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.chip{background:var(--accent);color:#fff;border-radius:999px;padding:1px 9px;font-size:11px;
white-space:nowrap}
.chip.seg{background:var(--ok)}
.chiprow{margin:6px 0;display:flex;gap:6px;flex-wrap:wrap}
.tdesc{color:var(--muted);font-size:12px;margin:4px 0 8px}
.sk{width:100%%;height:36px;display:block;margin-bottom:8px}
.sk.big{font-size:28px;font-weight:600;color:var(--accent);text-align:center;height:auto}
.sk.tbl .row{display:flex;gap:6px;margin-bottom:4px}
.sk.tbl span{height:7px;background:var(--line);border-radius:3px;flex:1}
details{font-size:12px}
summary{cursor:pointer;color:var(--accent)}
pre{white-space:pre-wrap;background:rgba(127,127,127,.1);padding:8px;border-radius:6px;
font-size:12px;overflow-x:auto}
.meta{color:var(--muted);font-size:11px;margin-top:6px}
.warn{color:var(--warn);font-size:12px}
table{width:100%%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
vertical-align:top;font-size:13px}
tr.error td{background:rgba(198,34,57,.08)}
tr.warning td{background:rgba(184,115,13,.08)}
code{font-size:12px}
ul{margin:0;padding-left:18px}
</style></head><body>
<header>
<h1>%(title)s</h1>
<p>%(description)s</p>
<div class="badges">
<span>tenant: %(tenant)s</span><span>cliente: %(client)s</span>
<span>audiencia: %(audience)s</span><span>dominios: %(domains)s</span>
<span>%(license)s</span><span>%(tilecount)s tiles de dados</span>
<span>gerado em %(generated)s</span>
</div>
</header>
<main>
%(deployment)s
<section><h2>Necessidades atendidas</h2>
<table><tr><th>#</th><th>Necessidade declarada</th><th>Tiles que respondem</th></tr>
%(requirements)s</table></section>

<section><h2>Previa do dashboard</h2><div class="grid">%(cards)s</div></section>

<section><h2>Segments</h2>
<table><tr><th>Nome</th><th>Filtros por modelo de dados</th><th>Status</th></tr>
%(segments)s</table></section>

<section><h2>Variaveis</h2>
<table><tr><th>Chave</th><th>Tipo</th><th>Selecao</th><th>Origem</th></tr>
%(variables)s</table></section>

<section><h2>Disponibilidade dos dados</h2>
%(deniedbanner)s
<p><strong>Metricas:</strong> %(metricsline)s</p>
<table><tr><th>Tabela Grail</th><th>Status</th><th>Permissao</th><th>Detalhe</th></tr>
%(permissions)s</table>
<p style="margin-top:12px"><strong>Tiles removidos por metrica inexistente</strong></p>
<table><tr><th>Tile</th><th>Metricas</th></tr>%(dropped)s</table>
</section>

<section><h2>Validacao</h2>
<table><tr><th>Nivel</th><th>Tile</th><th>Mensagem</th></tr>%(findings)s</table></section>

<section><h2>Validacao das DQL no tenant</h2>
<table><tr><th>Tile</th><th>Titulo</th><th>Status</th><th>Detalhe</th></tr>%(queries)s</table>
</section>

<section><h2>Observacoes</h2><ul>%(warnings)s</ul></section>

<section><h2>Fontes consultadas</h2>
<table><tr><th>Fonte</th><th>Documento</th><th>Caminho</th></tr>%(knowledge)s</table></section>

<section><h2>JSON do dashboard</h2>
<details><summary>ver JSON completo</summary><pre>%(json)s</pre></details></section>
</main></body></html>
"""
