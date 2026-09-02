"""Converte um DashboardSpec no documento JSON de dashboard da plataforma."""

from .spec import DashboardSpec, TileSpec, VariableSpec
from .version import DASHBOARD_CONTENT_VERSION

GRID_COLUMNS = 24


def pack_layout(tiles, columns=GRID_COLUMNS):
    """Distribui os tiles na grade de 24 colunas sem sobreposicao.

    Tiles markdown de largura total sempre iniciam uma nova linha (funcionam como
    cabecalhos de secao).
    """

    layouts = {}
    x = 0
    y = 0
    row_height = 0
    for tile in tiles:
        width = max(1, min(int(tile.width or 12), columns))
        height = max(1, int(tile.height or 6))
        full_row = tile.kind == "markdown" or width >= columns
        if full_row and x > 0:
            y += row_height
            x = 0
            row_height = 0
        if x + width > columns:
            y += row_height
            x = 0
            row_height = 0
        layouts[tile.tile_id] = {"x": x, "y": y, "w": width, "h": height}
        x += width
        row_height = max(row_height, height)
        if full_row:
            y += height
            x = 0
            row_height = 0
    return layouts


def build_tile(tile, segment_uids=None):
    if tile.kind == "markdown":
        return {"type": "markdown", "content": tile.markdown or ""}

    payload = {
        "type": "data",
        "title": tile.title or "",
        "query": tile.query or "",
        "visualization": tile.visualization or "table",
        "visualizationSettings": tile.visualization_settings or {},
        "querySettings": tile.query_settings or {},
    }
    if tile.description:
        payload["description"] = tile.description
    resolved = [segment_uids.get(key) for key in tile.segments] if segment_uids else []
    resolved = [uid for uid in resolved if uid]
    if resolved:
        payload["segments"] = resolved
    return payload


def build_variable(variable):
    payload = {
        "key": variable.key,
        "type": variable.var_type,
        "visible": bool(variable.visible),
        "editable": bool(variable.editable),
        "version": int(variable.version or 2),
    }
    if variable.var_type in ("query", "csv"):
        payload["input"] = variable.input
        payload["multiple"] = bool(variable.multiple)
        if variable.multiple and variable.default_value:
            payload["defaultValue"] = variable.default_value
    else:
        if variable.default_value:
            payload["defaultValue"] = variable.default_value
    return payload


def build_dashboard(spec, segment_uids=None, include_header_note=True):
    """Gera o documento completo ({name, type, content}) pronto para a API."""

    tiles = list(spec.tiles)
    if include_header_note and spec.default_timeframe:
        for tile in tiles:
            if tile.kind == "markdown":
                note = "\n\n_Periodo sugerido pelo solicitante: %s (ajuste no seletor de tempo)._" % (
                    spec.default_timeframe
                )
                if note.strip() not in (tile.markdown or ""):
                    tile.markdown = (tile.markdown or "") + note
                break

    content = {
        "version": DASHBOARD_CONTENT_VERSION,
        "variables": [build_variable(v) for v in spec.variables],
        "tiles": {t.tile_id: build_tile(t, segment_uids) for t in tiles},
        "layouts": pack_layout(tiles),
        "settings": {"gridLayout": {"columnsCount": GRID_COLUMNS}},
    }
    if spec.refresh_rate:
        content["refreshRate"] = spec.refresh_rate

    return {
        "name": spec.name,
        "type": "dashboard",
        "description": spec.description,
        "content": content,
    }


def dashboard_to_spec(document, name=None):
    """Converte um dashboard existente (JSON) de volta para um DashboardSpec.

    Usado para reaproveitar templates salvos como base de novos dashboards.
    """

    if not isinstance(document, dict):
        raise ValueError("documento invalido")
    content = document.get("content") if isinstance(document.get("content"), dict) else document
    tiles_map = content.get("tiles") or {}
    layouts = content.get("layouts") or {}

    tiles = []
    for tile_id, raw in sorted(tiles_map.items(), key=lambda kv: _layout_order(layouts, kv[0])):
        layout = layouts.get(tile_id) or {}
        kind = raw.get("type") or "data"
        if kind == "markdown":
            tiles.append(
                TileSpec(
                    tile_id=str(tile_id), kind="markdown",
                    markdown=raw.get("content") or "",
                    width=int(layout.get("w") or 24), height=int(layout.get("h") or 2),
                    title=(raw.get("content") or "").splitlines()[0].lstrip("# ").strip()[:80],
                )
            )
            continue
        tiles.append(
            TileSpec(
                tile_id=str(tile_id),
                kind="data",
                title=raw.get("title") or "",
                query=raw.get("query") or raw.get("input") or "",
                visualization=raw.get("visualization") or "table",
                visualization_settings=raw.get("visualizationSettings") or {},
                query_settings=raw.get("querySettings") or {},
                description=raw.get("description") or "",
                width=int(layout.get("w") or 12),
                height=int(layout.get("h") or 6),
                segments=list(raw.get("segments") or []),
            )
        )

    variables = [VariableSpec.from_dict(v) for v in content.get("variables") or []]
    return DashboardSpec(
        name=name or document.get("name") or "Dashboard importado",
        description=document.get("description") or "",
        tiles=tiles,
        variables=variables,
    )


def _layout_order(layouts, tile_id):
    layout = layouts.get(tile_id) or {}
    return (int(layout.get("y") or 0), int(layout.get("x") or 0), str(tile_id))
