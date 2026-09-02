"""Resolucao de chaves de metrica entre Grail (dt.*) e classico (builtin:*).

Contexto: na plataforma Grail as metricas nativas foram renomeadas - o prefixo
``builtin:`` virou ``dt.`` e camelCase virou snake_case
(docs.dynatrace.com -> "Built-in Metrics on Grail"). Nem toda metrica classica
tem equivalente em Grail e nem todo tenant tem "Metrics powered by Grail"
habilitado, entao a chave certa depende do tenant.

Este modulo le o indice de metricas do tenant **uma vez** e classifica cada chave
usada pelo catalogo:

``ok``       - a chave existe como esta
``alias``    - nao existe, mas o equivalente classico existe (a DQL e reescrita)
``missing``  - comprovadamente inexistente (o tile fica indisponivel)
``unknown``  - nao foi possivel verificar (sem permissao, indice vazio, offline)
"""

import re

from .errors import ApiError

OK = "ok"
ALIAS = "alias"
MISSING = "missing"
UNKNOWN = "unknown"

# Equivalencias curadas Grail -> classico. So sao aplicadas quando a chave
# classica realmente existe no indice do tenant.
METRIC_ALIASES = {
    "dt.host.cpu.usage": ["builtin:host.cpu.usage"],
    "dt.host.cpu.iowait": ["builtin:host.cpu.iowait"],
    "dt.host.memory.usage": ["builtin:host.mem.usage"],
    "dt.host.memory.avail.bytes": ["builtin:host.mem.avail"],
    "dt.host.disk.used.percent": ["builtin:host.disk.usedPct"],
    "dt.host.net.nic.packets.rx": ["builtin:host.net.nic.packetsRx"],
    "dt.host.net.nic.packets.tx": ["builtin:host.net.nic.packetsTx"],
    "dt.service.request.count": [
        "builtin:service.requestCount.total",
        "builtin:service.requestCount.server",
    ],
    "dt.service.request.failure_count": [
        "builtin:service.errors.total.count",
        "builtin:service.errors.server.count",
    ],
    "dt.service.request.response_time": [
        "builtin:service.response.time",
        "builtin:service.response.server",
    ],
    "dt.service.messaging.publish.count": ["builtin:service.messaging.publish.count"],
    "dt.service.messaging.receive.count": ["builtin:service.messaging.receive.count"],
    "dt.service.messaging.process.count": ["builtin:service.messaging.process.count"],
    "dt.service.messaging.process.failure_count": [
        "builtin:service.messaging.process.failure.count"
    ],
    "dt.kubernetes.pods": ["builtin:kubernetes.pods"],
    "dt.kubernetes.node.pods_allocatable": ["builtin:kubernetes.node.pods_allocatable"],
    "dt.kubernetes.container.cpu_usage": [
        "builtin:kubernetes.container.cpu_usage",
        "builtin:kubernetes.workload.cpu_usage",
    ],
    "dt.kubernetes.container.memory_working_set": [
        "builtin:kubernetes.container.memory_working_set",
        "builtin:kubernetes.workload.memory_working_set",
    ],
    "dt.kubernetes.container.restarts": ["builtin:kubernetes.container.restarts"],
    "dt.kubernetes.container.oom_kills": ["builtin:kubernetes.container.oom_kills"],
    "dt.frontend.request.count": ["builtin:apps.web.requestCount.browser"],
    "dt.frontend.error.count": ["builtin:apps.web.errorCount"],
    "dt.frontend.user_action.count": ["builtin:apps.web.actionCount.load"],
    "dt.frontend.user_action.duration": ["builtin:apps.web.actionDuration.load"],
    "dt.frontend.session.active.estimated_count": ["builtin:apps.web.countOfSessions"],
    "dt.frontend.user.active.estimated_count": ["builtin:apps.web.countOfUsers"],
}

# quantas chaves do indice puxar para resolucao e sugestoes
INDEX_LIMIT = 5000
INDEX_DQL = (
    "metrics\n"
    "| fields metric.key\n"
    "| limit %d" % INDEX_LIMIT
)
SUGGESTION_THRESHOLD = 0.72


class MetricResolution(object):
    def __init__(self, key, status=UNKNOWN, resolved="", reason="", suggestions=None):
        self.key = key
        self.status = status
        self.resolved = resolved or key
        self.reason = reason
        self.suggestions = suggestions or []

    @property
    def usable(self):
        return self.status in (OK, ALIAS, UNKNOWN)

    def to_dict(self):
        return {
            "key": self.key,
            "status": self.status,
            "resolved": self.resolved,
            "reason": self.reason,
            "suggestions": self.suggestions,
        }


class MetricCatalogView(object):
    """Indice de metricas do tenant + resolucao das chaves usadas nos tiles."""

    def __init__(self, index=None, available=None, reason=""):
        self.index = set(index or [])
        # available: True (indice lido), False (sem permissao), None (offline)
        self.available = available
        self.reason = reason
        self._cache = {}

    # ------------------------------------------------------------------ carga
    @classmethod
    def load(cls, client, capabilities=None):
        if client is None:
            return cls(available=None, reason="execucao offline")
        if capabilities is not None:
            readable = capabilities.table_readable("metrics")
            if readable is False:
                permission = (capabilities.tables.get("metrics") or {}).get("permission")
                return cls(available=False,
                           reason="sem permissao de leitura da tabela metrics (%s)"
                                  % (permission or "storage:metrics:read"))
        try:
            result = client.execute_query(INDEX_DQL, max_records=INDEX_LIMIT)
        except ApiError as exc:
            if getattr(exc, "unauthorized", False):
                return cls(available=False,
                           reason="sem permissao de leitura da tabela metrics "
                                  "(storage:metrics:read)")
            return cls(available=None, reason="falha ao ler o indice de metricas: %s" % exc)
        keys = [r.get("metric.key") for r in result.get("records") or []]
        keys = [k for k in keys if k]
        if not keys:
            return cls(available=False,
                       reason="o indice de metricas voltou vazio - metricas em Grail podem "
                              "nao estar habilitadas ou a permissao filtra todos os registros")
        return cls(index=keys, available=True)

    # ------------------------------------------------------------- resolucao
    def resolve(self, key):
        if key in self._cache:
            return self._cache[key]
        if self.available is not True:
            resolution = MetricResolution(key, UNKNOWN, reason=self.reason)
        elif key in self.index:
            resolution = MetricResolution(key, OK)
        else:
            alias = next((a for a in METRIC_ALIASES.get(key, []) if a in self.index), "")
            if alias:
                resolution = MetricResolution(
                    key, ALIAS, resolved=alias,
                    reason="chave Grail ausente; usando a equivalente classica",
                )
            else:
                resolution = MetricResolution(
                    key, MISSING,
                    reason="nao existe no indice de metricas do tenant",
                    suggestions=self.suggest(key),
                )
        self._cache[key] = resolution
        return resolution

    def resolve_all(self, keys):
        return {key: self.resolve(key) for key in sorted(set(keys))}

    def suggest(self, key, limit=3):
        """Chaves parecidas no tenant (apenas sugestao - nunca substituicao automatica)."""

        target = _tokens(key)
        if not target:
            return []
        scored = []
        for candidate in self.index:
            tokens = _tokens(candidate)
            if not tokens:
                continue
            score = len(target & tokens) / float(len(target | tokens))
            if score >= SUGGESTION_THRESHOLD:
                scored.append((score, candidate))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [candidate for _, candidate in scored[:limit]]

    def summary(self, resolutions):
        counts = {OK: 0, ALIAS: 0, MISSING: 0, UNKNOWN: 0}
        for resolution in resolutions.values():
            counts[resolution.status] = counts.get(resolution.status, 0) + 1
        return {
            "available": self.available,
            "reason": self.reason,
            "indexSize": len(self.index),
            "counts": counts,
        }


def _tokens(key):
    body = re.sub(r"^(dt\.|builtin:)", "", key or "")
    return {t for t in re.split(r"[^a-z0-9]+", body.lower()) if len(t) > 2}


def needs_backticks(key):
    return bool(re.search(r"[^A-Za-z0-9._]", key or ""))


def rewrite_query(query, resolutions):
    """Troca as chaves de metrica pela chave que existe no tenant."""

    if not query:
        return query
    for key, resolution in resolutions.items():
        if resolution.status != ALIAS or resolution.resolved == key:
            continue
        replacement = ("`%s`" % resolution.resolved if needs_backticks(resolution.resolved)
                       else resolution.resolved)
        query = re.sub(r"(?<![\w.`])%s(?![\w.])" % re.escape(key), replacement, query)
    return query
