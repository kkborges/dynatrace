"""Validacao do dashboard: estrutura, compatibilidade de visualizacao e DQL."""

import re

from . import dqlutil
from .builder import GRID_COLUMNS, build_dashboard

TIME_SERIES_VIZ = {"lineChart", "areaChart", "barChart", "bandChart"}
CATEGORICAL_VIZ = {"categoricalBarChart", "pieChart", "donutChart"}
SINGLE_VIZ = {"singleValue", "meterBar", "gauge"}
TABULAR_VIZ = {"table", "raw", "recordList"}
MAP_VIZ = {"choroplethMap", "dotMap", "connectionMap", "bubbleMap"}
MATRIX_VIZ = {"heatmap", "scatterplot"}
KNOWN_VIZ = (
    TIME_SERIES_VIZ | CATEGORICAL_VIZ | SINGLE_VIZ | TABULAR_VIZ | MAP_VIZ | MATRIX_VIZ
    | {"histogram", "honeycomb"}
)

TIME_HINTS = ("timeseries", "makeTimeseries", "bin(")


class Finding(object):
    def __init__(self, level, message, tile=None, rule=""):
        self.level = level          # error | warning | info
        self.message = message
        self.tile = tile
        self.rule = rule

    def to_dict(self):
        return {"level": self.level, "message": self.message, "tile": self.tile,
                "rule": self.rule}

    def __repr__(self):  # pragma: no cover
        return "<%s %s: %s>" % (self.level, self.tile or "-", self.message)


class ValidationReport(object):
    def __init__(self, findings=None, query_results=None):
        self.findings = findings or []
        self.query_results = query_results or []

    @property
    def errors(self):
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self):
        return [f for f in self.findings if f.level == "warning"]

    @property
    def ok(self):
        return not self.errors

    def add(self, level, message, tile=None, rule=""):
        self.findings.append(Finding(level, message, tile, rule))
        return self

    def to_dict(self):
        return {
            "ok": self.ok,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "findings": [f.to_dict() for f in self.findings],
            "queries": self.query_results,
        }


def validate_document(document):
    """Valida o JSON final do dashboard (estrutura da plataforma)."""

    report = ValidationReport()
    if not isinstance(document, dict):
        report.add("error", "documento nao e um objeto JSON")
        return report
    if not (document.get("name") or "").strip():
        report.add("error", "dashboard sem 'name'", rule="name")
    content = document.get("content")
    if not isinstance(content, dict):
        report.add("error", "documento sem 'content'", rule="content")
        return report

    tiles = content.get("tiles")
    layouts = content.get("layouts")
    if not isinstance(tiles, dict) or not tiles:
        report.add("error", "'content.tiles' vazio ou invalido", rule="tiles")
        return report
    if not isinstance(layouts, dict):
        report.add("error", "'content.layouts' ausente", rule="layouts")
        return report

    missing_layout = set(tiles) - set(layouts)
    orphan_layout = set(layouts) - set(tiles)
    for tile_id in sorted(missing_layout):
        report.add("error", "tile sem layout correspondente", tile=tile_id, rule="layout-parity")
    for tile_id in sorted(orphan_layout):
        report.add("error", "layout sem tile correspondente", tile=tile_id, rule="layout-parity")

    boxes = []
    for tile_id, layout in layouts.items():
        try:
            x, y = int(layout["x"]), int(layout["y"])
            w, h = int(layout["w"]), int(layout["h"])
        except (KeyError, TypeError, ValueError):
            report.add("error", "layout invalido (x/y/w/h)", tile=tile_id, rule="layout")
            continue
        if w <= 0 or h <= 0:
            report.add("error", "layout com largura/altura nao positiva", tile=tile_id,
                       rule="layout")
        if x < 0 or y < 0:
            report.add("error", "layout com coordenada negativa", tile=tile_id, rule="layout")
        if x + w > GRID_COLUMNS:
            report.add("error", "tile ultrapassa as %d colunas da grade" % GRID_COLUMNS,
                       tile=tile_id, rule="grid")
        boxes.append((tile_id, x, y, w, h))

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if _overlap(a, b):
                report.add("error", "tiles sobrepostos: %s e %s" % (a[0], b[0]),
                           tile=a[0], rule="overlap")

    declared = {v.get("key") for v in content.get("variables") or [] if v.get("key")}
    used = set()
    for tile in tiles.values():
        for match in re.finditer(r"\$([A-Za-z][A-Za-z0-9_]*)", tile.get("query") or ""):
            used.add(match.group(1))
    for key in sorted(declared - used):
        report.add("warning", "variavel '%s' declarada mas nao usada em nenhum tile" % key,
                   rule="variables")
    for key in sorted(used - declared):
        report.add("error", "query usa $%s mas a variavel nao esta declarada" % key,
                   rule="variables")

    for variable in content.get("variables") or []:
        if variable.get("type") in ("query", "csv") and not (variable.get("input") or "").strip():
            report.add("error", "variavel '%s' sem 'input'" % variable.get("key"),
                       rule="variables")

    for tile_id, tile in sorted(tiles.items()):
        report.findings.extend(_validate_tile(tile_id, tile))
    return report


def _overlap(a, b):
    _, ax, ay, aw, ah = a
    _, bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _validate_tile(tile_id, tile):
    findings = []
    kind = tile.get("type")
    if kind == "markdown":
        if not (tile.get("content") or "").strip():
            findings.append(Finding("warning", "tile markdown vazio", tile_id, "markdown"))
        return findings
    if kind not in ("data", "code", "slo"):
        findings.append(Finding("error", "tipo de tile desconhecido: %s" % kind, tile_id, "type"))
        return findings
    if kind != "data":
        return findings

    query = tile.get("query") or ""
    viz = tile.get("visualization") or ""
    if not query.strip():
        findings.append(Finding("error", "tile de dados sem query", tile_id, "query"))
    if viz not in KNOWN_VIZ:
        findings.append(Finding("warning", "visualizacao desconhecida: %s" % viz, tile_id, "viz"))

    lowered = query.lower()
    has_time = any(hint.lower() in lowered for hint in TIME_HINTS)
    has_summarize_by = bool(re.search(r"summarize[^|]*by\s*:", query, re.S))

    if viz in TIME_SERIES_VIZ and not has_time:
        findings.append(Finding(
            "error",
            "%s exige eixo temporal (timeseries/makeTimeseries/bin) na query" % viz,
            tile_id, "viz-compat"))
    if viz == "barChart" and has_summarize_by and not has_time:
        findings.append(Finding(
            "error", "use categoricalBarChart para valores por categoria (barChart e temporal)",
            tile_id, "viz-compat"))
    if viz in CATEGORICAL_VIZ and not (has_summarize_by or "fields" in lowered):
        findings.append(Finding(
            "warning", "%s espera categoria + valor (summarize ... by:{categoria})" % viz,
            tile_id, "viz-compat"))
    if viz in SINGLE_VIZ:
        record_field = (
            (tile.get("visualizationSettings") or {}).get("singleValue") or {}
        ).get("recordField")
        if not record_field:
            findings.append(Finding(
                "warning", "singleValue sem 'recordField' em visualizationSettings",
                tile_id, "viz-compat"))
        elif record_field not in query:
            findings.append(Finding(
                "warning", "recordField '%s' nao aparece na query" % record_field,
                tile_id, "viz-compat"))
        if re.match(r"^\s*timeseries", query.strip()) and "array" not in lowered \
                and "scalar" not in lowered:
            findings.append(Finding(
                "warning",
                "resultado de timeseries e array; reduza com arrayAvg/arraySum ou scalar:true",
                tile_id, "viz-compat"))
    if viz == "heatmap" and re.search(r"by\s*:\s*\{[^}]*bin\(\s*timestamp", query):
        findings.append(Finding(
            "warning", "heatmap nao aceita timestamp cru: use toString(bin(timestamp, 1h))",
            tile_id, "viz-compat"))

    if re.search(r"\bfrom\s*:\s*-?\d+[mhd]\b", query) or re.search(r"\bfrom\s*:\s*now\(\)", query):
        findings.append(Finding(
            "info",
            "a query fixa um periodo; o seletor de tempo do dashboard sera ignorado neste tile",
            tile_id, "timeframe"))

    for message in dqlutil.lint(query):
        findings.append(Finding("warning", message, tile_id, "dql-lint"))
    return findings


def validate_spec(spec, document=None):
    """Valida o spec + o documento gerado."""

    document = document or build_dashboard(spec)
    report = validate_document(document)
    if not spec.tiles:
        report.add("error", "spec sem tiles", rule="spec")
    for requirement in spec.uncovered_requirements():
        report.add("warning", "requisito sem tile associado: %s" % requirement.text[:120],
                   rule="coverage")
    for segment in spec.segments:
        if not segment.includes:
            report.add("warning", "segment '%s' sem filtros aplicaveis" % segment.name,
                       rule="segments")
        elif not segment.verified:
            report.add("info",
                       "segment '%s' usa campos nao verificados no tenant (%s)"
                       % (segment.name, ", ".join(
                           sorted({i["filter"].split(" ")[0] for i in segment.includes}))),
                       rule="segments")
    online = bool((spec.capabilities or {}).get("online"))
    unverified = sorted({m for t in spec.tiles for m in (t.unverified_metrics or [])})
    if unverified and not online:
        report.add(
            "info",
            "metricas nao verificadas (sem conexao com o tenant): %s"
            % ", ".join(unverified[:12]) + ("..." if len(unverified) > 12 else ""),
            rule="metrics",
        )
    elif online:
        for tile in spec.tiles:
            for metric in tile.unverified_metrics or []:
                report.add("warning", "metrica nao encontrada no tenant: %s" % metric,
                           tile=tile.tile_id, rule="metrics")
    return report


def validate_queries_live(spec, client, max_records=1, limit=None):
    """Valida as DQL no tenant (query:verify e, quando possivel, execucao)."""

    results = []
    queries = []
    for tile in spec.tiles:
        if tile.kind == "data" and (tile.query or "").strip():
            queries.append((tile.tile_id, tile.title, tile.query))
    for variable in spec.variables:
        if variable.var_type == "query" and variable.input.strip():
            queries.append(("var:%s" % variable.key, "variavel %s" % variable.key, variable.input))
    if limit:
        queries = queries[:limit]

    for tile_id, title, query in queries:
        entry = {"tile": tile_id, "title": title, "query": query, "status": "unknown"}
        probe = _resolve_variables(query, spec)
        try:
            verification = client.verify_query(probe)
        except Exception as exc:  # noqa: BLE001
            entry.update(status="error", message=str(exc))
            results.append(entry)
            continue
        if verification is not None:
            entry["syntax"] = "ok" if verification.get("valid") else "invalid"
            entry["notifications"] = verification.get("notifications") or []
            if not verification.get("valid"):
                entry["status"] = "invalid"
                results.append(entry)
                continue
        try:
            outcome = client.execute_query(probe, max_records=max_records)
            entry.update(
                status="ok",
                state=outcome.get("state"),
                records=len(outcome.get("records") or []),
            )
        except Exception as exc:  # noqa: BLE001
            entry.update(status="error", message=str(exc))
        results.append(entry)
    return results


def _resolve_variables(query, spec):
    """Substitui $Var por um valor plausivel para permitir a validacao."""

    def replace(match):
        key = match.group(1)
        variable = next((v for v in spec.variables if v.key == key), None)
        if variable and variable.var_type == "csv" and variable.input:
            return '"%s"' % variable.input.split(",")[0].strip()
        return '"*"'

    resolved = re.sub(r"\$([A-Za-z][A-Za-z0-9_]*)(?::\w+)?", replace, query or "")
    return resolved
