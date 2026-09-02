"""Usuarios e sessoes da interface web (somente biblioteca padrao).

Senhas sao guardadas como PBKDF2-HMAC-SHA256 com sal por usuario. Sessoes ficam
em memoria do processo: reiniciar o servidor desloga todo mundo, o que e o
comportamento desejado para uma ferramenta operacional.
"""

import hashlib
import hmac
import json
import os
import secrets
import stat
import time

from .errors import ConfigError

ITERATIONS = 240000
SESSION_TTL = 12 * 3600
USERS_FILE = "users.json"
ROLES = ("admin", "operador", "leitor")

# quem pode publicar no tenant / alterar cadastro
WRITE_ROLES = ("admin", "operador")
ADMIN_ROLES = ("admin",)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), ITERATIONS
    )
    return salt, digest.hex()


def verify_password(password, salt, expected):
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, expected or "")


class UserStore(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.path = os.path.join(workspace.state_dir, USERS_FILE)
        self.users = {}
        self.load()

    # ---------------------------------------------------------- persistencia
    def load(self):
        if not os.path.isfile(self.path):
            self.users = {}
            return self
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                self.users = json.load(handle).get("users") or {}
        except (OSError, ValueError) as exc:
            raise ConfigError("nao foi possivel ler %s: %s" % (self.path, exc))
        return self

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"users": self.users}, handle, ensure_ascii=False, indent=2)
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover
            pass
        return self.path

    # ---------------------------------------------------------------- gestao
    def empty(self):
        return not self.users

    def names(self):
        return sorted(self.users)

    def add(self, name, password, role="admin", full_name=""):
        name = (name or "").strip().lower()
        if not name:
            raise ConfigError("informe o nome de usuario")
        if role not in ROLES:
            raise ConfigError("papel invalido: %s (use %s)" % (role, ", ".join(ROLES)))
        if len(password or "") < 8:
            raise ConfigError("a senha precisa de ao menos 8 caracteres")
        salt, digest = hash_password(password)
        self.users[name] = {
            "name": name,
            "fullName": full_name or name,
            "role": role,
            "salt": salt,
            "hash": digest,
            "createdAt": time.time(),
        }
        self.save()
        return self.users[name]

    def set_password(self, name, password):
        user = self.get(name)
        if len(password or "") < 8:
            raise ConfigError("a senha precisa de ao menos 8 caracteres")
        salt, digest = hash_password(password)
        user.update(salt=salt, hash=digest, updatedAt=time.time())
        self.save()
        return user

    def remove(self, name):
        if name not in self.users:
            raise ConfigError("usuario '%s' nao encontrado" % name)
        if len(self.users) == 1:
            raise ConfigError("nao e possivel remover o unico usuario")
        self.users.pop(name)
        self.save()

    def get(self, name):
        user = self.users.get((name or "").strip().lower())
        if not user:
            raise ConfigError("usuario '%s' nao encontrado" % name)
        return user

    def authenticate(self, name, password):
        user = self.users.get((name or "").strip().lower())
        if not user:
            return None
        if not verify_password(password, user.get("salt"), user.get("hash")):
            return None
        return user

    def bootstrap_admin(self, name="admin"):
        """Cria o primeiro usuario com senha aleatoria e devolve (nome, senha)."""

        password = secrets.token_urlsafe(12)
        self.add(name, password, role="admin", full_name="Administrador")
        return name, password

    def public(self, user):
        return {"name": user.get("name"), "fullName": user.get("fullName"),
                "role": user.get("role")}


class SessionStore(object):
    def __init__(self, ttl=SESSION_TTL, clock=time.time):
        self.ttl = ttl
        self._clock = clock
        self.sessions = {}

    def create(self, user):
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {
            "user": user.get("name"),
            "role": user.get("role"),
            "fullName": user.get("fullName"),
            "expires": self._clock() + self.ttl,
        }
        return token

    def get(self, token):
        session = self.sessions.get(token or "")
        if not session:
            return None
        if session["expires"] < self._clock():
            self.sessions.pop(token, None)
            return None
        session["expires"] = self._clock() + self.ttl  # sessao deslizante
        return session

    def destroy(self, token):
        self.sessions.pop(token or "", None)

    def purge(self):
        now = self._clock()
        for token in [t for t, s in self.sessions.items() if s["expires"] < now]:
            self.sessions.pop(token, None)
