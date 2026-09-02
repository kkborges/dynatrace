"""Modelo intermediario: descricao do usuario -> DashboardSpec -> JSON Dynatrace."""

import re
import unicodedata
from dataclasses import dataclass, field, asdict


def slugify(value, maxlen=60):
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text or "dashboard")[:maxlen].strip("-")


@dataclass
class Requirement:
    """Uma necessidade declarada pelo solicitante."""

    req_id: str
    text: str
    keywords: list = field(default_factory=list)
    covered_by: list = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.req_id,
            "text": self.text,
            "keywords": self.keywords,
            "coveredBy": self.covered_by,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            req_id=data.get("id") or data.get("req_id") or "",
            text=data.get("text") or "",
            keywords=data.get("keywords") or [],
            covered_by=data.get("coveredBy") or [],
        )


@dataclass
class VariableSpec:
    key: str
    var_type: str = "query"          # query | csv | text
    input: str = ""
    multiple: bool = False
    default_value: str = ""
    visible: bool = True
    editable: bool = True
    version: int = 2
    description: str = ""

    def to_dict(self):
        return {
            "key": self.key,
            "type": self.var_type,
            "input": self.input,
            "multiple": self.multiple,
            "defaultValue": self.default_value,
            "visible": self.visible,
            "editable": self.editable,
            "version": self.version,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            key=data.get("key") or "",
            var_type=data.get("type") or data.get("var_type") or "query",
            input=data.get("input") or "",
            multiple=bool(data.get("multiple")),
            default_value=data.get("defaultValue") or data.get("default_value") or "",
            visible=data.get("visible", True),
            editable=data.get("editable", True),
            version=data.get("version", 2),
            description=data.get("description") or "",
        )


@dataclass
class SegmentSpec:
    """Filter-segment a ser criado no tenant e aplicado ao dashboard."""

    key: str                       # identificador interno
    name: str
    description: str = ""
    is_public: bool = True
    includes: list = field(default_factory=list)   # [{"dataObject":..,"filter":..}]
    dql_filter: str = ""           # expressao equivalente para embutir na DQL
    rationale: str = ""
    verified: bool = False         # campos verificados contra o tenant?
    uid: str = ""                  # preenchido apos criacao
    dimension: str = ""            # namespace | cluster | environment | ...
    value: str = ""                # valor concreto do recorte

    def to_dict(self):
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "isPublic": self.is_public,
            "includes": self.includes,
            "dqlFilter": self.dql_filter,
            "rationale": self.rationale,
            "verified": self.verified,
            "uid": self.uid,
            "dimension": self.dimension,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            key=data.get("key") or slugify(data.get("name", "")),
            name=data.get("name") or "",
            description=data.get("description") or "",
            is_public=data.get("isPublic", data.get("is_public", True)),
            includes=data.get("includes") or [],
            dql_filter=data.get("dqlFilter") or data.get("dql_filter") or "",
            rationale=data.get("rationale") or "",
            verified=bool(data.get("verified")),
            uid=data.get("uid") or "",
            dimension=data.get("dimension") or "",
            value=data.get("value") or "",
        )

    def api_payload(self):
        payload = {
            "name": self.name,
            "description": self.description,
            "isPublic": self.is_public,
            "includes": [
                {"dataObject": i["dataObject"], "filter": i["filter"]}
                for i in self.includes
                if i.get("dataObject") and i.get("filter")
            ],
        }
        return payload


@dataclass
class TileSpec:
    tile_id: str
    kind: str = "data"             # data | markdown
    title: str = ""
    query: str = ""
    visualization: str = "lineChart"
    visualization_settings: dict = field(default_factory=dict)
    query_settings: dict = field(default_factory=dict)
    markdown: str = ""
    description: str = ""
    width: int = 12
    height: int = 7
    section: str = ""
    blueprint: str = ""
    domain: str = ""
    signal: str = ""
    answers: list = field(default_factory=list)      # ids de Requirement
    segments: list = field(default_factory=list)     # uids de segment
    notes: list = field(default_factory=list)
    unverified_metrics: list = field(default_factory=list)
    availability: str = "ok"                # ok | unverified | missing
    metric_resolutions: list = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.tile_id,
            "kind": self.kind,
            "title": self.title,
            "query": self.query,
            "visualization": self.visualization,
            "visualizationSettings": self.visualization_settings,
            "querySettings": self.query_settings,
            "markdown": self.markdown,
            "description": self.description,
            "width": self.width,
            "height": self.height,
            "section": self.section,
            "blueprint": self.blueprint,
            "domain": self.domain,
            "signal": self.signal,
            "answers": self.answers,
            "segments": self.segments,
            "notes": self.notes,
            "unverifiedMetrics": self.unverified_metrics,
            "availability": self.availability,
            "metricResolutions": self.metric_resolutions,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            tile_id=str(data.get("id") or data.get("tile_id") or ""),
            kind=data.get("kind") or "data",
            title=data.get("title") or "",
            query=data.get("query") or "",
            visualization=data.get("visualization") or "lineChart",
            visualization_settings=data.get("visualizationSettings") or {},
            query_settings=data.get("querySettings") or {},
            markdown=data.get("markdown") or "",
            description=data.get("description") or "",
            width=int(data.get("width") or 12),
            height=int(data.get("height") or 7),
            section=data.get("section") or "",
            blueprint=data.get("blueprint") or "",
            domain=data.get("domain") or "",
            signal=data.get("signal") or "",
            answers=data.get("answers") or [],
            segments=data.get("segments") or [],
            notes=data.get("notes") or [],
            unverified_metrics=data.get("unverifiedMetrics") or [],
            availability=data.get("availability") or "ok",
            metric_resolutions=data.get("metricResolutions") or [],
        )


@dataclass
class DashboardSpec:
    name: str
    description: str = ""
    audience: str = "sre"
    request_text: str = ""
    requirements: list = field(default_factory=list)   # [Requirement]
    variables: list = field(default_factory=list)      # [VariableSpec]
    segments: list = field(default_factory=list)       # [SegmentSpec]
    tiles: list = field(default_factory=list)          # [TileSpec]
    tags: list = field(default_factory=list)
    domains: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    knowledge_sources: list = field(default_factory=list)
    tenant: str = ""
    client_name: str = ""
    capabilities: dict = field(default_factory=dict)
    segment_mode: str = "tile"                         # tile | dql | both
    metrics_summary: dict = field(default_factory=dict)
    dropped_tiles: list = field(default_factory=list)
    default_timeframe: str = ""                        # ex.: "now()-24h" (opcional)
    refresh_rate: str = ""

    # ------------------------------------------------------------------ utils
    @property
    def slug(self):
        return slugify(self.name)

    def data_tiles(self):
        return [t for t in self.tiles if t.kind == "data"]

    def coverage(self):
        """Mapa requisito -> tiles que o respondem."""

        by_req = {r.req_id: [] for r in self.requirements}
        for tile in self.tiles:
            for req_id in tile.answers:
                by_req.setdefault(req_id, []).append(tile.tile_id)
        return by_req

    def uncovered_requirements(self):
        coverage = self.coverage()
        return [r for r in self.requirements if not coverage.get(r.req_id)]

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "audience": self.audience,
            "requestText": self.request_text,
            "requirements": [r.to_dict() for r in self.requirements],
            "variables": [v.to_dict() for v in self.variables],
            "segments": [s.to_dict() for s in self.segments],
            "tiles": [t.to_dict() for t in self.tiles],
            "tags": self.tags,
            "domains": self.domains,
            "warnings": self.warnings,
            "knowledgeSources": self.knowledge_sources,
            "tenant": self.tenant,
            "clientName": self.client_name,
            "capabilities": self.capabilities,
            "segmentMode": self.segment_mode,
            "metricsSummary": self.metrics_summary,
            "droppedTiles": self.dropped_tiles,
            "defaultTimeframe": self.default_timeframe,
            "refreshRate": self.refresh_rate,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name") or "Dashboard",
            description=data.get("description") or "",
            audience=data.get("audience") or "sre",
            request_text=data.get("requestText") or "",
            requirements=[Requirement.from_dict(r) for r in data.get("requirements") or []],
            variables=[VariableSpec.from_dict(v) for v in data.get("variables") or []],
            segments=[SegmentSpec.from_dict(s) for s in data.get("segments") or []],
            tiles=[TileSpec.from_dict(t) for t in data.get("tiles") or []],
            tags=data.get("tags") or [],
            domains=data.get("domains") or [],
            warnings=data.get("warnings") or [],
            knowledge_sources=data.get("knowledgeSources") or [],
            tenant=data.get("tenant") or "",
            client_name=data.get("clientName") or "",
            capabilities=data.get("capabilities") or {},
            segment_mode=data.get("segmentMode") or "tile",
            metrics_summary=data.get("metricsSummary") or {},
            dropped_tiles=data.get("droppedTiles") or [],
            default_timeframe=data.get("defaultTimeframe") or "",
            refresh_rate=data.get("refreshRate") or "",
        )


def spec_asdict(obj):  # pragma: no cover - utilitario
    return asdict(obj)
