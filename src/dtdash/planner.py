"""Planner: descricao em linguagem natural -> DashboardSpec.

Le a descricao do solicitante (portugues ou ingles), identifica dominios,
audiencia, filtros e requisitos, consulta a base de conhecimento e as
capacidades do tenant, e monta a especificacao do dashboard - incluindo
variaveis e segments.
"""

import re
import unicodedata

from . import catalog
from .capabilities import TenantCapabilities
from .metrics import ALIAS, MISSING, OK, UNKNOWN, MetricCatalogView, rewrite_query
from .dqlutil import equals, inject_filters, variable_filter
from .spec import (
    DashboardSpec,
    Requirement,
    SegmentSpec,
    TileSpec,
    VariableSpec,
    slugify,
)

# ------------------------------------------------------------------- lexicos

DOMAIN_KEYWORDS = {
    "hosts": [
        "host", "hosts", "servidor", "servidores", "infra", "infraestrutura",
        "cpu", "memoria", "disco", "maquina", "maquinas", "vm", "vms",
        "capacidade", "saturacao", "sistema operacional", "ec2", "compute",
    ],
    "kubernetes": [
        "kubernetes", "k8s", "cluster", "clusters", "namespace", "namespaces",
        "pod", "pods", "container", "containers", "openshift", "workload",
        "deployment", "node", "nodes", "crashloop", "oom", "helm", "eks", "aks", "gke",
    ],
    "services": [
        "servico", "servicos", "service", "services", "aplicacao", "aplicacoes",
        "api", "apis", "microservico", "microservicos", "latencia", "tempo de resposta",
        "throughput", "requisicao", "requisicoes", "erro", "erros", "falha", "falhas",
        "taxa de erro", "disponibilidade", "backend", "sla", "slo", "golden signals",
        "sinais de ouro", "performance", "desempenho", "lentidao",
        "fila", "filas", "mensageria", "messaging", "kafka", "rabbitmq", "sqs", "topico",
    ],
    "spans": [
        "trace", "traces", "tracing", "span", "spans", "distributed tracing",
        "transacao", "transacoes", "endpoint", "endpoints", "operacao", "operacoes",
    ],
    "logs": [
        "log", "logs", "logging", "mensagem", "mensagens", "excecao", "excecoes",
        "exception", "stacktrace", "severidade", "grail", "ingestao de log",
    ],
    "problems": [
        "problema", "problemas", "problem", "problems", "davis", "incidente",
        "incidentes", "alerta", "alertas", "alarme", "anomalia", "anomalias",
        "mttr", "plantao", "noc", "on-call", "impacto",
    ],
    "rum": [
        "usuario", "usuarios", "user", "users", "rum", "real user", "experiencia",
        "frontend", "front-end", "browser", "navegador", "sessao", "sessoes",
        "web vitals", "lcp", "cls", "inp", "mobile", "app", "jornada", "pagina", "paginas",
    ],
    "database": [
        "banco", "bancos", "database", "db", "sql", "oracle", "postgres", "mysql",
        "mongodb", "query lenta", "consulta lenta",
    ],
    "security": [
        "seguranca", "security", "vulnerabilidade", "vulnerabilidades", "cve",
        "risco", "appsec", "compliance", "ameaca", "ataque", "exposicao",
    ],
    "bizevents": [
        "negocio", "business", "bizevent", "bizevents", "receita", "venda", "vendas",
        "pedido", "pedidos", "conversao", "funil", "transacao de negocio", "checkout",
        "carrinho", "kpi de negocio",
    ],
    "dps": [
        "dps", "custo", "custos", "billing", "faturamento", "licenca", "licencas",
        "finops", "chargeback", "showback", "gasto", "gastos", "orcamento",
        "capacidade contratada", "cost center", "centro de custo",
        "consumo da plataforma", "consumo dps", "consumo de dados", "consumo de licenca",
        "custo de query", "custo de consulta", "ingestao",
    ],
}

AUDIENCE_KEYWORDS = {
    "exec": [
        "executivo", "executiva", "diretoria", "diretor", "gestao", "gerencia",
        "board", "c-level", "cio", "cto", "negocio", "alta gestao", "resumo gerencial",
    ],
    "sre": [
        "sre", "operacao", "operacoes", "noc", "plantao", "on-call", "monitoracao",
        "monitoramento", "infraestrutura", "producao", "incidente", "war room",
    ],
    "dev": [
        "desenvolvimento", "desenvolvedor", "desenvolvedores", "dev", "devs",
        "squad", "time de produto", "engenharia", "debug", "troubleshooting",
    ],
    "finops": [
        "finops", "custo", "custos", "consumo", "billing", "faturamento",
        "chargeback", "showback", "orcamento", "dps",
    ],
}

DOMAIN_LABELS = {
    "hosts": "Infraestrutura",
    "kubernetes": "Kubernetes",
    "services": "Servicos",
    "spans": "Transacoes",
    "logs": "Logs",
    "problems": "Problemas",
    "rum": "Experiencia do usuario",
    "database": "Banco de dados",
    "security": "Seguranca",
    "bizevents": "Negocio",
    "dps": "Consumo DPS",
}

DIMENSION_LABELS = {
    "namespace": "Namespace",
    "cluster": "Cluster",
    "workload": "Workload",
    "service": "Servico",
    "host": "Host",
    "application": "Aplicacao",
    "environment": "Ambiente",
}

AUDIENCE_TITLE = {
    "exec": "Executivo",
    "sre": "SRE",
    "dev": "Engenharia",
    "finops": "FinOps",
}

# tamanho minimo de um dashboard util e dominios usados para completar
MIN_TILES = 6
COMPLEMENTARY_DOMAINS = ["problems", "services", "logs"]

VARIABLE_DIMENSION = {
    "Namespace": "namespace",
    "Cluster": "cluster",
    "Servico": "service",
    "Host": "host",
    "Aplicacao": "application",
}

# modelos baseados em registro: o campo existe no esquema do objeto
RECORD_OBJECTS = {
    "logs", "spans", "events", "bizevents", "security.events", "user.events",
    "user.sessions", "dt.davis.problems", "dt.davis.events", "dt.system.events",
}

TIMEFRAME_PATTERNS = [
    (re.compile(r"ultim[oa]s?\s+(\d+)\s*(minuto|minutos|min)\b"), "m"),
    (re.compile(r"ultim[oa]s?\s+(\d+)\s*(hora|horas|h)\b"), "h"),
    (re.compile(r"ultim[oa]s?\s+(\d+)\s*(dia|dias|d)\b"), "d"),
    (re.compile(r"last\s+(\d+)\s*(minute|minutes|min)\b"), "m"),
    (re.compile(r"last\s+(\d+)\s*(hour|hours|h)\b"), "h"),
    (re.compile(r"last\s+(\d+)\s*(day|days|d)\b"), "d"),
]

ENVIRONMENT_WORDS = {
    "producao": "producao",
    "production": "producao",
    "prod": "producao",
    "homologacao": "homologacao",
    "homolog": "homologacao",
    "staging": "staging",
    "stage": "staging",
    "qa": "qa",
    "desenvolvimento": "desenvolvimento",
    "dev": "desenvolvimento",
    "sandbox": "sandbox",
}

# extracao de valores concretos
VALUE_PATTERNS = [
    ("namespace", re.compile(r"namespaces?\s+(?:chamad[oa]\s+|de\s+|do\s+|da\s+)?[\"']?([a-z0-9][a-z0-9._-]{1,60})[\"']?")),
    ("cluster", re.compile(r"clusters?\s+(?:chamad[oa]\s+|de\s+|do\s+|da\s+)?[\"']?([a-z0-9][a-z0-9._-]{1,60})[\"']?")),
    ("workload", re.compile(r"(?:workload|deployment)s?\s+[\"']?([a-z0-9][a-z0-9._-]{1,60})[\"']?")),
    ("service", re.compile(r"servi[cç]os?\s+(?:chamad[oa]\s+|de\s+nome\s+)?[\"']([^\"']{2,60})[\"']")),
    ("host", re.compile(r"hosts?\s+[\"']([^\"']{2,60})[\"']")),
    ("application", re.compile(r"aplica[cç][aã]o\s+[\"']([^\"']{2,60})[\"']")),
]

STOP_VALUES = {
    "de", "do", "da", "para", "com", "que", "e", "ou", "no", "na", "em", "dos", "das",
    "kubernetes", "k8s", "todos", "todas", "cada", "por", "the", "of", "and", "all",
    "prod", "producao", "production",
}


def normalize(text):
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower()


def split_requirements(text):
    """Quebra a descricao em requisitos individuais."""

    raw = re.split(r"(?:\n\s*[-*•\d]+[.)]?\s+|\n{2,}|;|\.\s+|\n)", text or "")
    items = []
    for chunk in raw:
        chunk = chunk.strip(" \t-*•")
        if len(chunk) < 8:
            continue
        items.append(chunk)
    if not items and (text or "").strip():
        items = [text.strip()]
    return items


class Analysis(object):
    """Resultado da leitura da descricao."""

    def __init__(self):
        self.requirements = []
        self.domain_scores = {}
        self.domains = []
        self.audience = "sre"
        self.filters = {}          # dimensao -> valor concreto
        self.dimensions = []       # dimensoes citadas sem valor (viram variaveis)
        self.timeframe = ""
        self.wants_segments = True
        self.wants_dps = False
        self.title_hint = ""

    def to_dict(self):
        return {
            "requirements": [r.to_dict() for r in self.requirements],
            "domainScores": self.domain_scores,
            "domains": self.domains,
            "audience": self.audience,
            "filters": self.filters,
            "dimensions": self.dimensions,
            "timeframe": self.timeframe,
            "wantsDps": self.wants_dps,
        }


class Planner(object):
    def __init__(self, knowledge=None, client=None, capabilities=None):
        self.knowledge = knowledge
        self.client = client
        self.capabilities = capabilities or TenantCapabilities.offline()

    # ------------------------------------------------------------- analise
    def analyze(self, text):
        analysis = Analysis()
        norm = normalize(text)

        for index, chunk in enumerate(split_requirements(text), start=1):
            keywords = [k for k in re.split(r"[^a-z0-9.]+", normalize(chunk)) if len(k) > 3]
            analysis.requirements.append(
                Requirement(req_id="R%d" % index, text=chunk.strip(), keywords=keywords)
            )

        # dominios
        for domain, words in DOMAIN_KEYWORDS.items():
            score = 0
            for word in words:
                hits = len(re.findall(r"\b%s\b" % re.escape(word), norm))
                if hits:
                    score += hits * (2 if len(word) > 6 else 1)
            if score:
                analysis.domain_scores[domain] = score
        analysis.domains = [
            d for d, _ in sorted(
                analysis.domain_scores.items(), key=lambda kv: kv[1], reverse=True
            )
        ]

        # audiencia
        best_audience, best_score = "sre", 0
        for audience, words in AUDIENCE_KEYWORDS.items():
            score = sum(1 for w in words if re.search(r"\b%s\b" % re.escape(w), norm))
            if score > best_score:
                best_audience, best_score = audience, score
        analysis.audience = best_audience
        analysis.wants_dps = "dps" in analysis.domain_scores

        # janela de tempo sugerida
        for pattern, unit in TIMEFRAME_PATTERNS:
            match = pattern.search(norm)
            if match:
                analysis.timeframe = "now()-%s%s" % (match.group(1), unit)
                break

        # filtros concretos
        for dimension, pattern in VALUE_PATTERNS:
            match = pattern.search(norm)
            if match:
                value = match.group(1).strip()
                if value and value not in STOP_VALUES and not value.isdigit():
                    analysis.filters[dimension] = value

        for word, canonical in ENVIRONMENT_WORDS.items():
            if re.search(r"\b%s\b" % re.escape(word), norm):
                analysis.filters.setdefault("environment", canonical)
                break

        # dimensoes citadas sem valor -> viram variaveis de dashboard
        dimension_words = {
            "namespace": ["namespace", "namespaces"],
            "cluster": ["cluster", "clusters"],
            "service": ["servico", "servicos", "service", "services"],
            "host": ["host", "hosts", "servidor", "servidores"],
            "application": ["aplicacao", "aplicacoes", "application", "frontend"],
        }
        for dimension, words in dimension_words.items():
            if dimension in analysis.filters:
                continue
            if any(re.search(r"\b%s\b" % w, norm) for w in words):
                analysis.dimensions.append(dimension)

        if re.search(r"\b(sem\s+segment|nao\s+criar\s+segment|no\s+segments?)\b", norm):
            analysis.wants_segments = False

        analysis.title_hint = self._title_hint(text, analysis)
        return analysis

    def _title_hint(self, text, analysis):
        """Titulo curto e legivel a partir dos dominios detectados."""

        labels = [DOMAIN_LABELS.get(d, d.capitalize()) for d in analysis.domains[:3]]
        if labels:
            if len(labels) == 1:
                return labels[0]
            return "%s e %s" % (", ".join(labels[:-1]), labels[-1])
        return "Visao geral"

    # -------------------------------------------------------------- plano
    def plan(self, text, name=None, tenant="", client_name="", segment_mode="tile",
             max_tiles=None, audience=None, base_spec=None, extra_domains=None,
             on_missing="drop"):
        analysis = self.analyze(text)
        if audience:
            analysis.audience = audience

        caps = self.capabilities
        domains = self._select_domains(analysis, caps, extra_domains)

        spec = DashboardSpec(
            name=name or self._dashboard_name(analysis),
            description=self._description(analysis, domains),
            audience=analysis.audience,
            request_text=text or "",
            requirements=analysis.requirements,
            domains=domains,
            tenant=tenant,
            client_name=client_name,
            capabilities=caps.to_dict(),
            segment_mode=segment_mode,
            default_timeframe=analysis.timeframe,
            tags=self._tags(analysis, domains),
        )

        # 1. segments a partir dos filtros concretos
        if analysis.wants_segments and analysis.filters:
            spec.segments = self._build_segments(analysis, caps, spec.name)

        # 2. variaveis a partir das dimensoes citadas sem valor
        variables = self._build_variables(analysis, caps)

        # 3. tiles
        blueprints = self._select_blueprints(analysis, domains, caps, max_tiles)
        if base_spec is not None:
            spec.warnings.append(
                "Template base '%s' usado como ponto de partida." % base_spec.name
            )
        tiles = self._build_tiles(
            blueprints, analysis, spec, variables, base_spec=base_spec
        )
        spec.tiles = tiles

        # 4. mantem apenas variaveis efetivamente usadas
        used = set()
        for tile in tiles:
            for match in re.finditer(r"\$([A-Za-z][A-Za-z0-9_]*)", tile.query or ""):
                used.add(match.group(1))
        spec.variables = [v for v in variables if v.key in used]
        dropped = [v.key for v in variables if v.key not in used]
        if dropped:
            spec.warnings.append(
                "Variaveis descartadas por nao serem usadas em nenhum tile: %s"
                % ", ".join(dropped)
            )

        # 5. cobertura dos requisitos
        self._map_coverage(spec, analysis)

        # 6. resolucao das metricas contra o indice do tenant
        self._resolve_metrics(spec, on_missing=on_missing)

        # 7. conhecimento consultado
        spec.knowledge_sources = self._knowledge_sources(text, domains)

        # 8. avisos de licenciamento/DPS
        self._license_notes(spec, analysis, caps)
        return spec

    # ----------------------------------------------------------- internos
    def _select_domains(self, analysis, caps, extra_domains=None):
        domains = list(analysis.domains)
        for extra in extra_domains or []:
            if extra not in domains:
                domains.append(extra)
        if not domains:
            domains = ["services", "problems", "hosts"]

        # dominios que dependem de dados indisponiveis sao removidos
        available = []
        for domain in domains:
            if domain == "dps":
                if caps.dps is False and not analysis.wants_dps:
                    continue
            required = {
                "logs": "logs",
                "spans": "spans",
                "bizevents": "bizevents",
                "security": "security.events",
                "problems": "dt.davis.problems",
                "rum": "user.events",
                "database": "spans",
                "dps": "dt.system.events",
            }.get(domain)
            if required and caps.online and not caps.has_object(required):
                continue
            available.append(domain)
        if not available:
            available = ["services"]

        limit = {"exec": 3, "finops": 3, "dev": 4, "sre": 5}.get(analysis.audience, 4)
        # dominios explicitamente citados tem prioridade
        return available[: max(limit, 1)]

    def _dashboard_name(self, analysis):
        hint = analysis.title_hint or "Visao geral"
        parts = [hint]
        scope = analysis.filters.get("namespace") or analysis.filters.get("cluster")
        if scope:
            parts.append(scope)
        env = analysis.filters.get("environment")
        if env:
            parts.append(env.capitalize())
        prefix = AUDIENCE_TITLE.get(analysis.audience, "")
        name = " - ".join(parts)
        if prefix:
            name = "%s | %s" % (prefix, name)
        return name[:110]

    def _description(self, analysis, domains):
        return (
            "Dashboard gerado pelo dtdash a partir da descricao do solicitante. "
            "Dominios: %s. Audiencia: %s."
            % (", ".join(domains) or "-", analysis.audience)
        )

    def _tags(self, analysis, domains):
        tags = ["dtdash"] + list(domains)
        if analysis.filters.get("environment"):
            tags.append(analysis.filters["environment"])
        tags.append(analysis.audience)
        return sorted(set(tags))

    # ------------------------------------------------------------ segments
    def _build_segments(self, analysis, caps, dashboard_name):
        segments = []
        objects = ["logs", "spans", "events", "dt.davis.problems"]
        for dimension, value in sorted(analysis.filters.items()):
            includes = []
            dql_parts = []
            verified = True
            for data_object in objects:
                if caps.online and not caps.has_object(data_object):
                    continue
                candidates = catalog.FIELD_MAP.get(dimension, {}).get(data_object)
                if not candidates:
                    candidates = catalog.FIELD_MAP.get(dimension, {}).get("logs")
                if not candidates:
                    continue
                field_name, ok = caps.pick_field(data_object, candidates, client=self.client)
                verified = verified and ok
                if not field_name:
                    continue
                includes.append(
                    {"dataObject": data_object, "filter": equals(field_name, value)}
                )
                if not dql_parts:
                    dql_parts.append(equals(field_name, value))
            if not includes:
                continue
            name = "%s %s" % (DIMENSION_LABELS.get(dimension, dimension.capitalize()), value)
            segments.append(
                SegmentSpec(
                    key="%s-%s" % (dimension, slugify(value)),
                    name=name[:80],
                    description="Recorte automatico por %s = %s (dtdash)" % (dimension, value),
                    is_public=True,
                    includes=includes,
                    dql_filter=dql_parts[0] if dql_parts else "",
                    rationale="Filtro '%s' identificado na descricao do solicitante." % dimension,
                    verified=verified,
                    dimension=dimension,
                    value=value,
                )
            )
        return segments

    # ----------------------------------------------------------- variaveis
    VARIABLE_SOURCES = {
        "namespace": ("Namespace", "smartscapeNodes K8S_NAMESPACE | fields name | sort name asc"),
        "cluster": ("Cluster", "smartscapeNodes K8S_CLUSTER | fields name | sort name asc"),
        "service": ("Servico", "smartscapeNodes SERVICE | fields name | sort name asc"),
        "host": ("Host", "smartscapeNodes HOST | fields name | sort name asc"),
        "application": (
            "Aplicacao",
            "fetch user.events\n| filter isNotNull(frontend.name)\n"
            "| dedup frontend.name\n| fields frontend.name\n| sort frontend.name asc\n| limit 100",
        ),
    }

    def _build_variables(self, analysis, caps):
        variables = []
        for dimension in analysis.dimensions:
            source = self.VARIABLE_SOURCES.get(dimension)
            if not source:
                continue
            key, query = source
            variables.append(
                VariableSpec(
                    key=key,
                    var_type="query",
                    input=query,
                    multiple=True,
                    default_value="3420b2ac-f1cf-4b24-b62d-61ba1ba8ed05*",
                    description="Filtro dinamico por %s" % dimension,
                )
            )
        return variables

    # --------------------------------------------------------------- tiles
    def _select_blueprints(self, analysis, domains, caps, max_tiles=None):
        limit = max_tiles or {"exec": 9, "finops": 8, "dev": 12, "sre": 14}.get(
            analysis.audience, 12
        )
        norm_request = normalize(analysis.requirements and
                                 " ".join(r.text for r in analysis.requirements) or "")

        scored = []
        for bp in catalog.CATALOG:
            if bp.domain not in domains:
                continue
            if bp.dps_only and caps.dps is False and not analysis.wants_dps:
                continue
            if bp.requires and caps.online:
                if any(not caps.has_object(obj) for obj in bp.requires):
                    continue
            if analysis.audience not in bp.audiences:
                continue
            score = float(bp.priority)
            score += 12 * (len(domains) - domains.index(bp.domain))
            for keyword in bp.keywords:
                if re.search(r"\b%s\b" % re.escape(keyword), norm_request):
                    score += 14
            if analysis.audience == "exec" and bp.visualization in ("singleValue", "meterBar"):
                score += 25
            if analysis.audience in ("sre", "dev") and bp.visualization == "table":
                score += 8
            scored.append((score, bp))

        scored.sort(key=lambda item: (-item[0], item[1].bp_id))
        selected = []
        per_domain = {}
        domain_cap = max(2, limit // max(1, len(domains)) + 1)
        for score, bp in scored:
            if len(selected) >= limit:
                break
            if per_domain.get(bp.domain, 0) >= domain_cap:
                continue
            selected.append(bp)
            per_domain[bp.domain] = per_domain.get(bp.domain, 0) + 1

        # garante ao menos um KPI de resumo
        if not any(bp.visualization == "singleValue" for bp in selected):
            for score, bp in scored:
                if bp.visualization == "singleValue":
                    selected.insert(0, bp)
                    break

        # dashboards muito pequenos ganham tiles complementares de contexto
        if len(selected) < MIN_TILES:
            selected.extend(
                self._complementary(selected, domains, caps, analysis,
                                    MIN_TILES - len(selected))
            )
        return selected

    def _complementary(self, selected, domains, caps, analysis, needed):
        """Completa dashboards curtos com contexto de saude do ambiente."""

        chosen = {bp.bp_id for bp in selected}
        extras = []
        for domain in COMPLEMENTARY_DOMAINS:
            if domain in domains:
                continue
            for bp in sorted(catalog.by_domain(domain), key=lambda b: -b.priority):
                if len(extras) >= needed:
                    return extras
                if bp.bp_id in chosen or bp.dps_only:
                    continue
                if bp.requires and caps.online:
                    if any(not caps.has_object(obj) for obj in bp.requires):
                        continue
                extras.append(bp)
        return extras

    def _build_tiles(self, blueprints, analysis, spec, variables, base_spec=None):
        tiles = []
        counter = [0]

        def next_id():
            counter[0] += 1
            return str(counter[0])

        # cabecalho do dashboard
        header = [
            "# %s" % spec.name,
            "",
            spec.description,
        ]
        if spec.segments:
            header.append(
                "\n**Segments aplicados:** %s"
                % ", ".join(s.name for s in spec.segments)
            )
        if analysis.requirements:
            header.append("\n**Perguntas que este dashboard responde:**")
            for req in analysis.requirements[:8]:
                header.append("- %s" % req.text)
        tiles.append(
            TileSpec(
                tile_id=next_id(), kind="markdown", markdown="\n".join(header),
                width=24, height=max(3, min(8, 2 + len(analysis.requirements[:8]))),
                section="Resumo executivo", title=spec.name,
            )
        )

        # tiles herdados de um template base
        if base_spec is not None:
            for tile in base_spec.tiles:
                if tile.kind != "data":
                    continue
                clone = TileSpec.from_dict(tile.to_dict())
                clone.tile_id = next_id()
                clone.notes = list(clone.notes) + ["herdado do template base"]
                tiles.append(clone)

        sections_seen = set()
        ordered = sorted(blueprints, key=lambda bp: (self._section_rank(bp, spec), -bp.priority))
        for bp in ordered:
            if bp.section and bp.section not in sections_seen:
                sections_seen.add(bp.section)
                tiles.append(
                    TileSpec(
                        tile_id=next_id(), kind="markdown",
                        markdown="## %s" % bp.section, width=24, height=2,
                        section=bp.section, title=bp.section,
                    )
                )
            tiles.append(self._tile_from_blueprint(bp, next_id(), analysis, spec, variables))
        return tiles

    def _section_rank(self, blueprint, spec):
        """Resumo executivo primeiro, DPS por ultimo, o resto na ordem dos dominios."""

        if blueprint.section == "Resumo executivo":
            return -1
        if blueprint.domain == "dps":
            return 900
        try:
            return spec.domains.index(blueprint.domain)
        except ValueError:
            return 500

    def _tile_from_blueprint(self, bp, tile_id, analysis, spec, variables):
        query = bp.query
        target = bp.filter_target()
        expressions = []
        notes = []

        # filtros de segment embutidos na DQL (modo dql/both)
        if spec.segment_mode in ("dql", "both"):
            for segment in spec.segments:
                expr = self._segment_expression(segment, target, query)
                if expr:
                    expressions.append(expr)

        # filtros de variavel
        for variable in variables:
            field_name = self._variable_field(variable.key, target, query)
            if not field_name:
                continue
            if field_name in query and "$%s" % variable.key in query:
                continue
            expressions.append(variable_filter(field_name, variable.key, variable.multiple))

        if expressions:
            query = inject_filters(query, expressions, bp.source_kind)

        segments = []
        if spec.segment_mode in ("tile", "both"):
            segments = [s.key for s in spec.segments]

        if bp.notes:
            notes.extend(bp.notes)

        return TileSpec(
            tile_id=tile_id,
            kind="data",
            title=bp.title,
            query=query,
            visualization=bp.visualization,
            visualization_settings=dict(bp.visualization_settings or {}),
            query_settings={},
            description=bp.question,
            width=bp.width,
            height=bp.height,
            section=bp.section,
            blueprint=bp.bp_id,
            domain=bp.domain,
            signal=bp.signal,
            segments=segments,
            notes=notes,
        )

    def _segment_expression(self, segment, data_object, query=""):
        dimension = segment.dimension or segment.key.split("-", 1)[0]
        field_name = self._dimension_field(dimension, data_object, query)
        if not field_name or not segment.value:
            return None
        return equals(field_name, segment.value)

    def _variable_field(self, variable_key, data_object, query=""):
        dimension = VARIABLE_DIMENSION.get(variable_key)
        if not dimension or not data_object:
            return None
        return self._dimension_field(dimension, data_object, query)

    def _dimension_field(self, dimension, data_object, query=""):
        """Campo a usar para filtrar `dimension` em `data_object`.

        Em modelos de registro (logs, spans, eventos...) o campo sempre existe no
        esquema, entao basta escolher o melhor candidato. Em metricas e smartscape
        o filtro so e seguro quando a dimensao ja aparece na propria query - caso
        contrario o filtro pode nao existir naquela metrica/tipo de no.
        """

        candidates = catalog.FIELD_MAP.get(dimension, {}).get(data_object)
        if not candidates:
            return None
        if data_object in RECORD_OBJECTS:
            field_name, _ = self.capabilities.pick_field(
                data_object, candidates, client=self.client
            )
            return field_name
        for candidate in candidates:
            if re.search(r"(?<![\w.])%s(?![\w.])" % re.escape(candidate), query or ""):
                return candidate
        return None

    # ------------------------------------------------------------ cobertura
    def _map_coverage(self, spec, analysis):
        for req in spec.requirements:
            req_words = set(req.keywords)
            req_norm = normalize(req.text)
            best = []
            for tile in spec.tiles:
                if tile.kind != "data":
                    continue
                bp = catalog.CATALOG_BY_ID.get(tile.blueprint)
                score = 0
                if bp:
                    for keyword in bp.keywords:
                        if re.search(r"\b%s\b" % re.escape(keyword), req_norm):
                            score += 2
                    if bp.domain in analysis.domains[:2]:
                        score += 1
                title_words = set(normalize(tile.title).split())
                score += len(req_words & title_words)
                if score > 0:
                    best.append((score, tile))
            best.sort(key=lambda item: -item[0])
            for _, tile in best[:3]:
                if req.req_id not in tile.answers:
                    tile.answers.append(req.req_id)
                if tile.tile_id not in req.covered_by:
                    req.covered_by.append(tile.tile_id)

        uncovered = [r for r in spec.requirements if not r.covered_by]
        for req in uncovered:
            spec.warnings.append(
                "Requisito sem tile dedicado (revise a previa): \"%s\""
                % (req.text[:120])
            )

    # ------------------------------------------------------------- metricas
    def _resolve_metrics(self, spec, on_missing="drop"):
        """Confere cada chave de metrica no tenant e ajusta os tiles.

        * chave existe -> nada a fazer
        * so existe a equivalente classica (builtin:) -> reescreve a DQL
        * comprovadamente ausente -> tile marcado e, por padrao, removido
        * impossivel verificar (sem permissao/offline) -> tile mantido e sinalizado
        """

        keys = set()
        for tile in spec.tiles:
            blueprint = catalog.CATALOG_BY_ID.get(tile.blueprint)
            if blueprint:
                keys.update(blueprint.metrics)
        if not keys:
            return

        view = MetricCatalogView.load(
            self.client if self.capabilities.online else None, self.capabilities
        )
        resolutions = view.resolve_all(keys)
        spec.metrics_summary = view.summary(resolutions)
        spec.metrics_summary["resolutions"] = {
            key: resolution.to_dict() for key, resolution in sorted(resolutions.items())
        }

        if view.available is not True:
            for tile in spec.tiles:
                blueprint = catalog.CATALOG_BY_ID.get(tile.blueprint)
                if blueprint and blueprint.metrics:
                    tile.unverified_metrics = list(blueprint.metrics)
                    tile.availability = "unverified"
            spec.warnings.append(
                "Metricas nao verificadas: %s. Os tiles foram mantidos - confirme os "
                "graficos apos a publicacao." % (view.reason or "motivo desconhecido")
            )
            return

        aliased, missing_tiles = [], []
        for tile in spec.tiles:
            blueprint = catalog.CATALOG_BY_ID.get(tile.blueprint)
            if not blueprint or not blueprint.metrics:
                continue
            tile_resolutions = {k: resolutions[k] for k in blueprint.metrics if k in resolutions}
            tile.metric_resolutions = [r.to_dict() for r in tile_resolutions.values()
                                       if r.status != OK]
            ausentes = [k for k, r in tile_resolutions.items() if r.status == MISSING]
            trocadas = [(k, r.resolved) for k, r in tile_resolutions.items() if r.status == ALIAS]
            if trocadas:
                tile.query = rewrite_query(tile.query, tile_resolutions)
                tile.notes.append(
                    "chave(s) classica(s) usada(s): %s"
                    % ", ".join("%s -> %s" % (k, v) for k, v in trocadas)
                )
                aliased.extend(k for k, _ in trocadas)
            if ausentes:
                tile.availability = "missing"
                tile.unverified_metrics = ausentes
                missing_tiles.append(tile)

        if aliased:
            spec.warnings.append(
                "Tenant sem as metricas Grail correspondentes; o dtdash usou as chaves "
                "classicas equivalentes em %d tile(s): %s"
                % (len({t.tile_id for t in spec.tiles if t.notes and any(
                    n.startswith("chave(s) classica") for n in t.notes)}),
                   ", ".join(sorted(set(aliased))[:6]))
            )

        if missing_tiles:
            self._apply_missing_policy(spec, missing_tiles, resolutions, on_missing)

    def _apply_missing_policy(self, spec, missing_tiles, resolutions, on_missing):
        detalhes = []
        for tile in missing_tiles:
            faltantes = []
            for key in tile.unverified_metrics:
                resolution = resolutions.get(key)
                sugestao = ""
                if resolution and resolution.suggestions:
                    sugestao = " (parecidas no tenant: %s)" % ", ".join(resolution.suggestions)
                faltantes.append("%s%s" % (key, sugestao))
            detalhes.append("%s [%s]" % (tile.title, "; ".join(faltantes)))

        if on_missing == "keep":
            spec.warnings.append(
                "%d tile(s) mantidos apesar de a metrica nao existir no tenant "
                "(--on-missing keep): %s" % (len(missing_tiles), " | ".join(detalhes))
            )
            return

        removidos = {tile.tile_id for tile in missing_tiles}
        spec.dropped_tiles = [
            {"id": tile.tile_id, "title": tile.title, "blueprint": tile.blueprint,
             "metrics": list(tile.unverified_metrics)}
            for tile in missing_tiles
        ]
        spec.tiles = [tile for tile in spec.tiles if tile.tile_id not in removidos]
        self._drop_empty_sections(spec)
        spec.warnings.append(
            "%d tile(s) removidos por dependerem de metricas inexistentes no tenant "
            "(use --on-missing keep para manter): %s"
            % (len(missing_tiles), " | ".join(detalhes))
        )

    def _drop_empty_sections(self, spec):
        """Remove cabecalhos de secao que ficaram sem tiles de dados."""

        mantidos = []
        for index, tile in enumerate(spec.tiles):
            if tile.kind != "markdown" or not (tile.markdown or "").startswith("## "):
                mantidos.append(tile)
                continue
            tem_dados = False
            for seguinte in spec.tiles[index + 1:]:
                if seguinte.kind == "markdown" and (seguinte.markdown or "").startswith("## "):
                    break
                if seguinte.kind == "data":
                    tem_dados = True
                    break
            if tem_dados:
                mantidos.append(tile)
        spec.tiles = mantidos

    # ---------------------------------------------------------- conhecimento
    def _knowledge_sources(self, text, domains):
        if not self.knowledge:
            return []
        query = "%s %s" % (text or "", " ".join(domains))
        hits = self.knowledge.search(query, limit=8)
        return [hit.to_dict() for hit in hits]

    def _license_notes(self, spec, analysis, caps):
        if caps.dps is True:
            spec.warnings.append(
                "Consumo DPS detectado: analises via Grail/logs e tiles de consumo estao habilitados."
            )
        elif caps.dps is False:
            spec.warnings.append(
                "Nenhum evento de consumo DPS nas ultimas 24h. Isso NAO prova ausencia de "
                "licenca (eventos de billing medem consumo, nao entitlement) - confirme em "
                "Account Management > Subscription."
            )
        else:
            spec.warnings.append(
                "Licenciamento/DPS nao verificado (sem conexao com o tenant nesta execucao)."
            )
