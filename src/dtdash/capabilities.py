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
            errors=data.get("errors") or [],
            checked_at=data.get("checkedAt") or 0.0,
        )
