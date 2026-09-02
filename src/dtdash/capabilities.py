"""Deteccao das capacidades do tenant (Grail, data objects, DPS).

Regra importante (documentacao Dynatrace / skill dt-platform-costs): eventos de
billing registram *consumo*, nunca *entitlement*. A ausencia de eventos NAO
prova ausencia de licenca - por isso o resultado e tri-estado:
``dps = True | False | None`` (None = nao foi possivel determinar).
"""

import time
from dataclasses import dataclass, field

from .errors import ApiError

# data objects tipicos de um tenant Grail (usados quando nao ha conexao)
DEFAULT_DATA_OBJECTS = [
    "logs",
    "spans",
    "events",
    "bizevents",
    "user.sessions",
    "user.events",
    "security.events",
    "dt.davis.problems",
    "dt.davis.events",
    "dt.entity.host",
    "dt.entity.service",
    "dt.system.events",
]

# tabela Grail -> permissao necessaria (docs: "Permissions in Grail")
TABLE_PERMISSIONS = {
    "logs": "storage:logs:read",
    "spans": "storage:spans:read",
    "events": "storage:events:read",
    "bizevents": "storage:bizevents:read",
    "security.events": "storage:security.events:read",
    "user.events": "storage:user.events:read",
    "user.sessions": "storage:user.sessions:read",
    "metrics": "storage:metrics:read",
    "smartscape": "storage:smartscape:read",
    "entities": "storage:entities:read",
    "dt.davis.problems": "storage:events:read",
    "dt.davis.events": "storage:events:read",
    "dt.system.events": "storage:system:read",
}

# sondas de 1 registro por tabela (janela curta para nao gerar consumo relevante)
TABLE_PROBES = [
    ("metrics", "metrics\n| fields metric.key\n| limit 1"),
    ("smartscape", 'smartscapeNodes "HOST"\n| fields name\n| limit 1'),
    ("logs", "fetch logs, from:-15m\n| fields timestamp\n| limit 1"),
    ("spans", "fetch spans, from:-15m\n| fields start_time\n| limit 1"),
    ("events", "fetch events, from:-15m\n| fields timestamp\n| limit 1"),
    ("dt.davis.problems", "fetch dt.davis.problems, from:-24h\n| fields event.start\n| limit 1"),
    ("bizevents", "fetch bizevents, from:-15m\n| fields timestamp\n| limit 1"),
    ("user.events", "fetch user.events, from:-15m\n| fields timestamp\n| limit 1"),
    ("security.events", "fetch security.events, from:-24h\n| fields timestamp\n| limit 1"),
    ("dt.system.events", "fetch dt.system.events, from:-24h\n| fields timestamp\n| limit 1"),
]

STATUS_OK = "ok"            # consultavel e com dados
STATUS_EMPTY = "empty"      # consultavel, sem dados na janela
STATUS_DENIED = "denied"    # 403 / NOT_AUTHORIZED_FOR_TABLE
STATUS_ERROR = "error"      # outra falha

DPS_PROBE_DQL = (
    "fetch dt.system.events, from:-24h\n"
    "| filter event.kind == \"BILLING_USAGE_EVENT\"\n"
    "| summarize events = count(), by:{event.type}\n"
    "| sort events desc\n"
    "| limit 10"
)


@dataclass
class TenantCapabilities:
    """Snapshot do que o tenant oferece para o planejamento do dashboard."""

    online: bool = False
    environment_id: str = ""
    data_objects: list = field(default_factory=lambda: list(DEFAULT_DATA_OBJECTS))
    dps: object = None                      # True / False / None (desconhecido)
    dps_event_types: list = field(default_factory=list)
    grail_queryable: bool = False
    fields_by_object: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)   # tabela -> {status, detail, permission}
    errors: list = field(default_factory=list)
    checked_at: float = 0.0

    # ------------------------------------------------------------------ probes
    @classmethod
    def offline(cls, environment_id=""):
        return cls(online=False, environment_id=environment_id, checked_at=time.time())

    @classmethod
    def probe(cls, client, deep=True):
        caps = cls(online=True, environment_id=client.profile.environment_id,
                   checked_at=time.time())
        try:
            objects = client.data_objects()
            if objects:
                caps.data_objects = objects
                caps.grail_queryable = True
        except ApiError as exc:
            caps.errors.append("data_objects: %s" % exc)

        if deep:
            caps.tables = probe_tables(client)
            try:
                result = client.execute_query(DPS_PROBE_DQL, max_records=10)
                records = result.get("records") or []
                caps.dps = bool(records)
                caps.dps_event_types = [
                    r.get("event.type") for r in records if r.get("event.type")
                ]
                caps.grail_queryable = True
            except ApiError as exc:
                caps.errors.append("dps: %s" % exc)
                caps.dps = None
        return caps

    # ----------------------------------------------------------------- helpers
    def has_object(self, name):
        if not self.online:
            return name in DEFAULT_DATA_OBJECTS
        return name in self.data_objects

    def known_fields(self, name):
        return self.fields_by_object.get(name) or []

    def field_exists(self, data_object, field_name, client=None):
        """True/False quando conhecido; None quando nao foi possivel verificar."""

        fields = self.fields_by_object.get(data_object)
        if fields is None and client is not None:
            try:
                fields = client.describe(data_object)
                self.fields_by_object[data_object] = fields
            except ApiError as exc:
                self.errors.append("describe %s: %s" % (data_object, exc))
                self.fields_by_object[data_object] = []
                fields = []
        if not fields:
            return None
        return field_name in fields

    def pick_field(self, data_object, candidates, client=None):
        """Escolhe o primeiro campo existente no tenant (ou o primeiro candidato)."""

        for candidate in candidates:
            exists = self.field_exists(data_object, candidate, client=client)
            if exists:
                return candidate, True
        return (candidates[0] if candidates else ""), False

    # ------------------------------------------------------------ permissoes
    def table_status(self, table):
        return (self.tables.get(table) or {}).get("status")

    def table_readable(self, table):
        """True/False quando conhecido; None quando nao foi sondado."""

        status = self.table_status(table)
        if status is None:
            return None
        return status in (STATUS_OK, STATUS_EMPTY)

    def denied_tables(self):
        return sorted(t for t, info in self.tables.items()
                      if info.get("status") == STATUS_DENIED)

    def missing_permissions(self):
        return sorted({info.get("permission") for t, info in self.tables.items()
                       if info.get("status") == STATUS_DENIED and info.get("permission")})

    def license_label(self):
        if self.dps is True:
            return "DPS (consumo de plataforma detectado)"
        if self.dps is False:
            return "DPS nao detectado nas ultimas 24h (pode ser licenca classica ou sem consumo)"
        return "Licenciamento nao verificado"

    def to_dict(self):
        return {
            "online": self.online,
            "environmentId": self.environment_id,
            "grailQueryable": self.grail_queryable,
            "dataObjects": self.data_objects,
            "dps": self.dps,
            "dpsEventTypes": self.dps_event_types,
            "tables": self.tables,
            "deniedTables": self.denied_tables(),
            "missingPermissions": self.missing_permissions(),
            "licenseLabel": self.license_label(),
            "errors": self.errors,
            "checkedAt": self.checked_at,
        }

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            online=bool(data.get("online")),
            environment_id=data.get("environmentId") or "",
            data_objects=data.get("dataObjects") or list(DEFAULT_DATA_OBJECTS),
            dps=data.get("dps"),
            dps_event_types=data.get("dpsEventTypes") or [],
            grail_queryable=bool(data.get("grailQueryable")),
            tables=data.get("tables") or {},
            errors=data.get("errors") or [],
            checked_at=data.get("checkedAt") or 0.0,
        )


def probe_tables(client):
    """Sonda cada tabela Grail e classifica: ok / vazia / sem permissao / erro."""

    out = {}
    for table, dql in TABLE_PROBES:
        permission = TABLE_PERMISSIONS.get(table, "")
        try:
            result = client.execute_query(dql, max_records=1)
        except ApiError as exc:
            if getattr(exc, "unauthorized", False):
                out[table] = {
                    "status": STATUS_DENIED,
                    "permission": permission,
                    "detail": "sem permissao de leitura (%s)" % (permission or exc.code),
                    "code": exc.code,
                }
            else:
                out[table] = {"status": STATUS_ERROR, "permission": permission,
                              "detail": str(exc)[:200], "code": getattr(exc, "code", "")}
            continue
        records = result.get("records") or []
        out[table] = {
            "status": STATUS_OK if records else STATUS_EMPTY,
            "permission": permission,
            "detail": "1 registro lido" if records else "consultavel, sem dados na janela",
            "code": "",
        }
    return out
