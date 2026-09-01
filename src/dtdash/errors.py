"""Excecoes do dtdash."""


class DtDashError(Exception):
    """Erro base."""


class ConfigError(DtDashError):
    """Configuracao ausente ou invalida."""


class AuthError(DtDashError):
    """Falha de autenticacao com o tenant."""


class ApiError(DtDashError):
    """Erro retornado por uma API do Dynatrace."""

    def __init__(self, message, status=None, url=None, payload=None):
        super().__init__(message)
        self.status = status
        self.url = url
        self.payload = payload

    def __str__(self):  # pragma: no cover - formatacao
        base = super().__str__()
        if self.status:
            return "[HTTP %s] %s (%s)" % (self.status, base, self.url or "")
        return base


class ValidationError(DtDashError):
    """Dashboard/spec invalido."""


class PlanningError(DtDashError):
    """Nao foi possivel planejar um dashboard a partir da descricao."""


class NotFoundError(DtDashError):
    """Recurso local nao encontrado (proposta, template...)."""
