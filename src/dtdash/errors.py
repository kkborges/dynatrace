"""Excecoes do dtdash."""


class DtDashError(Exception):
    """Erro base."""


class ConfigError(DtDashError):
    """Configuracao ausente ou invalida."""


class AuthError(DtDashError):
    """Falha de autenticacao com o tenant."""


class ApiError(DtDashError):
    """Erro retornado por uma API do Dynatrace."""

    def __init__(self, message, status=None, url=None, payload=None, code=""):
        super().__init__(message)
        self.status = status
        self.url = url
        self.payload = payload
        self.code = code or _error_code(payload)

    @property
    def unauthorized(self):
        return self.status == 403 or self.code in (
            "NOT_AUTHORIZED_FOR_TABLE", "NOT_AUTHORIZED_FOR_BUCKET",
            "NOT_AUTHORIZED_FOR_RECORD", "MISSING_PERMISSION",
        )

    def __str__(self):  # pragma: no cover - formatacao
        base = super().__str__()
        if self.status:
            return "[HTTP %s] %s (%s)" % (self.status, base, self.url or "")
        return base


def _error_code(payload):
    """Extrai o codigo de erro do Grail (ex.: NOT_AUTHORIZED_FOR_TABLE)."""

    if not isinstance(payload, dict):
        return ""
    error = payload.get("error") if isinstance(payload.get("error"), dict) else payload
    for key in ("errorType", "type", "code", "message"):
        value = error.get(key)
        if isinstance(value, str) and value.isupper() and "_" in value:
            return value
    details = error.get("details")
    if isinstance(details, dict):
        for key in ("errorType", "code", "type"):
            value = details.get(key)
            if isinstance(value, str) and value.isupper():
                return value
    return ""


class ValidationError(DtDashError):
    """Dashboard/spec invalido."""


class PlanningError(DtDashError):
    """Nao foi possivel planejar um dashboard a partir da descricao."""


class NotFoundError(DtDashError):
    """Recurso local nao encontrado (proposta, template...)."""
