"""Configuracao, workspace e perfis de tenant."""

import json
import os
import re
import stat
from dataclasses import dataclass, field, asdict

from .errors import ConfigError

CONFIG_DIRNAME = ".dtdash"
CONFIG_FILENAME = "config.json"

DEFAULT_SCOPES = [
    # documentos (dashboards)
    "document:documents:read",
    "document:documents:write",
    "document:documents:delete",
    "document:environment-shares:write",
    # segments
    "storage:filter-segments:read",
    "storage:filter-segments:write",
    "storage:filter-segments:share",
    # Grail / DQL
    "storage:buckets:read",
    "storage:logs:read",
    "storage:metrics:read",
    "storage:events:read",
    "storage:entities:read",
    "storage:spans:read",
    "storage:bizevents:read",
    "storage:system:read",
    "storage:user.events:read",
    "storage:user.sessions:read",
    "storage:security.events:read",
    "storage:smartscape:read",
]

_ENV_ID_RE = re.compile(r"^[a-z0-9]{3,}$", re.IGNORECASE)


def _norm_url(url):
    if not url:
        return None
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


@dataclass
class TenantProfile:
    """Perfil de acesso a um tenant Dynatrace."""

    name: str
    environment_id: str = ""
    platform_url: str = ""          # https://<env>.apps.dynatrace.com
    environment_url: str = ""       # https://<env>.live.dynatrace.com (APIs classicas)
    auth_method: str = "platform_token"   # platform_token | oauth
    platform_token: str = ""              # valor literal (evite; prefira env)
    platform_token_env: str = "DT_PLATFORM_TOKEN"
    oauth_client_id: str = ""
    oauth_client_id_env: str = "DT_OAUTH_CLIENT_ID"
    oauth_client_secret: str = ""
    oauth_client_secret_env: str = "DT_OAUTH_CLIENT_SECRET"
    oauth_account_urn: str = ""           # urn:dtaccount:<uuid>
    sso_url: str = "https://sso.dynatrace.com/sso/oauth2/token"
    scopes: list = field(default_factory=lambda: list(DEFAULT_SCOPES))
    client_name: str = ""                 # nome do cliente/empresa (biblioteca de templates)
    verify_tls: bool = True
    notes: str = ""

    # ------------------------------------------------------------------ helpers
    @classmethod
    def from_dict(cls, data):
        known = {f for f in cls.__dataclass_fields__}  # noqa: F821
        payload = {k: v for k, v in (data or {}).items() if k in known}
        if "name" not in payload:
            raise ConfigError("perfil de tenant sem 'name'")
        profile = cls(**payload)
        profile.normalize()
        return profile

    def to_dict(self, redact=True):
        data = asdict(self)
        if redact:
            for key in ("platform_token", "oauth_client_secret"):
                if data.get(key):
                    data[key] = "***"
        return data

    def normalize(self):
        self.platform_url = _norm_url(self.platform_url) or ""
        self.environment_url = _norm_url(self.environment_url) or ""
        if not self.environment_id:
            for url in (self.platform_url, self.environment_url):
                if url:
                    host = url.split("//", 1)[-1]
                    self.environment_id = host.split(".", 1)[0]
                    break
        if self.environment_id and not self.platform_url:
            self.platform_url = "https://%s.apps.dynatrace.com" % self.environment_id
        if self.environment_id and not self.environment_url:
            self.environment_url = "https://%s.live.dynatrace.com" % self.environment_id
        if not self.client_name:
            self.client_name = self.name
        return self

    # ------------------------------------------------------------- credenciais
    def resolve_platform_token(self):
        return self.platform_token or os.environ.get(self.platform_token_env or "", "")

    def resolve_oauth_client_id(self):
        return self.oauth_client_id or os.environ.get(self.oauth_client_id_env or "", "")

    def resolve_oauth_client_secret(self):
        return self.oauth_client_secret or os.environ.get(
            self.oauth_client_secret_env or "", ""
        )

    def has_credentials(self):
        if self.auth_method == "platform_token":
            return bool(self.resolve_platform_token())
        return bool(self.resolve_oauth_client_id() and self.resolve_oauth_client_secret())

    def dashboard_url(self, document_id):
        return "%s/ui/apps/dynatrace.dashboards/dashboard/%s" % (
            self.platform_url,
            document_id,
        )

    def validate(self):
        if not self.platform_url:
            raise ConfigError(
                "tenant '%s': informe --environment-id ou --platform-url" % self.name
            )
        if not self.has_credentials():
            if self.auth_method == "platform_token":
                raise ConfigError(
                    "tenant '%s': token de plataforma ausente (defina %s no ambiente)"
                    % (self.name, self.platform_token_env)
                )
            raise ConfigError(
                "tenant '%s': credenciais OAuth ausentes (defina %s e %s)"
                % (self.name, self.oauth_client_id_env, self.oauth_client_secret_env)
            )
        return self


def find_workspace(start=None):
    """Descobre a raiz do workspace (repo do dtdash ou diretorio corrente)."""

    env_home = os.environ.get("DTDASH_HOME")
    if env_home:
        return os.path.abspath(env_home)
    here = os.path.abspath(start or os.getcwd())
    probe = here
    while True:
        markers = [
            os.path.join(probe, "src", "dtdash"),
            os.path.join(probe, CONFIG_DIRNAME),
        ]
        if any(os.path.isdir(m) for m in markers):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return here
        probe = parent


class Workspace:
    """Diretorios usados pela ferramenta."""

    def __init__(self, root=None):
        self.root = os.path.abspath(root or find_workspace())

    # diretorios ------------------------------------------------------------
    @property
    def state_dir(self):
        return os.path.join(self.root, CONFIG_DIRNAME)

    @property
    def config_path(self):
        return os.path.join(self.state_dir, CONFIG_FILENAME)

    @property
    def proposals_dir(self):
        return os.path.join(self.state_dir, "proposals")

    @property
    def knowledge_dir(self):
        return os.path.join(self.root, "knowledge")

    @property
    def knowledge_cache_dir(self):
        return os.path.join(self.knowledge_dir, "cache")

    @property
    def knowledge_seed_dir(self):
        return os.path.join(self.knowledge_dir, "seed")

    @property
    def knowledge_uploads_dir(self):
        return os.path.join(self.knowledge_dir, "uploads")

    @property
    def examples_dir(self):
        return os.path.join(self.root, "examples")

    @property
    def dashboards_dir(self):
        return os.path.join(self.root, "dashboards")

    @property
    def library_dir(self):
        return os.path.join(self.dashboards_dir, "library")

    @property
    def clients_dir(self):
        return os.path.join(self.dashboards_dir, "clients")

    def ensure(self):
        for path in (
            self.state_dir,
            self.proposals_dir,
            self.knowledge_dir,
            self.knowledge_cache_dir,
            self.knowledge_seed_dir,
            self.knowledge_uploads_dir,
            self.examples_dir,
            self.library_dir,
            self.clients_dir,
        ):
            os.makedirs(path, exist_ok=True)
        return self


class Config:
    """Configuracao persistida (perfis de tenant + preferencias)."""

    def __init__(self, workspace=None, data=None):
        self.workspace = workspace or Workspace()
        self.data = data if data is not None else {"tenants": {}, "settings": {}}

    # persistencia ----------------------------------------------------------
    @classmethod
    def load(cls, workspace=None):
        ws = workspace or Workspace()
        data = {"tenants": {}, "settings": {}}
        for path in (
            os.path.join(os.path.expanduser("~"), CONFIG_DIRNAME, CONFIG_FILENAME),
            ws.config_path,
        ):
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        chunk = json.load(handle)
                except (OSError, ValueError) as exc:
                    raise ConfigError("nao foi possivel ler %s: %s" % (path, exc))
                data.setdefault("tenants", {}).update(chunk.get("tenants") or {})
                data.setdefault("settings", {}).update(chunk.get("settings") or {})
        cfg = cls(ws, data)
        cfg._merge_env_tenant()
        return cfg

    def save(self):
        self.workspace.ensure()
        payload = json.dumps(self.data, indent=2, ensure_ascii=False, sort_keys=True)
        with open(self.workspace.config_path, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
        try:
            os.chmod(self.workspace.config_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover - sistemas sem chmod
            pass
        return self.workspace.config_path

    # tenants ---------------------------------------------------------------
    def _merge_env_tenant(self):
        """Permite operar 100% por variaveis de ambiente (CI/CD)."""

        env_id = os.environ.get("DT_ENVIRONMENT_ID") or os.environ.get("DT_ENVIRONMENT")
        if not env_id:
            return
        name = os.environ.get("DTDASH_TENANT_NAME", "env")
        profile = {
            "name": name,
            "environment_id": env_id if _ENV_ID_RE.match(env_id) else "",
            "platform_url": os.environ.get("DT_PLATFORM_URL", "")
            or ("" if _ENV_ID_RE.match(env_id) else env_id),
            "environment_url": os.environ.get("DT_ENVIRONMENT_URL", ""),
            "auth_method": os.environ.get("DT_AUTH_METHOD", "")
            or ("oauth" if os.environ.get("DT_OAUTH_CLIENT_ID") else "platform_token"),
            "oauth_account_urn": os.environ.get("DT_OAUTH_ACCOUNT_URN", ""),
            "client_name": os.environ.get("DTDASH_CLIENT_NAME", "") or name,
        }
        self.data.setdefault("tenants", {}).setdefault(name, profile)
        self.data.setdefault("settings", {}).setdefault("default_tenant", name)

    def tenant_names(self):
        return sorted((self.data.get("tenants") or {}).keys())

    def get_tenant(self, name=None):
        tenants = self.data.get("tenants") or {}
        if not name:
            name = self.data.get("settings", {}).get("default_tenant")
        if not name:
            if len(tenants) == 1:
                name = next(iter(tenants))
            else:
                raise ConfigError(
                    "nenhum tenant informado. Use --tenant ou 'dtdash tenants add'."
                )
        if name not in tenants:
            raise ConfigError(
                "tenant '%s' nao encontrado. Disponiveis: %s"
                % (name, ", ".join(self.tenant_names()) or "(nenhum)")
            )
        return TenantProfile.from_dict(dict(tenants[name], name=name))

    def try_get_tenant(self, name=None):
        try:
            return self.get_tenant(name)
        except ConfigError:
            return None

    def put_tenant(self, profile):
        profile.normalize()
        data = asdict(profile)
        data.pop("name", None)
        self.data.setdefault("tenants", {})[profile.name] = data
        if not self.data.setdefault("settings", {}).get("default_tenant"):
            self.data["settings"]["default_tenant"] = profile.name
        return profile

    def remove_tenant(self, name):
        tenants = self.data.setdefault("tenants", {})
        if name not in tenants:
            raise ConfigError("tenant '%s' nao encontrado" % name)
        tenants.pop(name)
        if self.data.get("settings", {}).get("default_tenant") == name:
            self.data["settings"]["default_tenant"] = next(iter(tenants), "")

    def set_default_tenant(self, name):
        if name not in (self.data.get("tenants") or {}):
            raise ConfigError("tenant '%s' nao encontrado" % name)
        self.data.setdefault("settings", {})["default_tenant"] = name

    # preferencias ----------------------------------------------------------
    def setting(self, key, default=None):
        return (self.data.get("settings") or {}).get(key, default)

    def set_setting(self, key, value):
        self.data.setdefault("settings", {})[key] = value
