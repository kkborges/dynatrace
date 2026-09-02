"""Interface web do dtdash (servidor da biblioteca padrao).

Fluxo: entrar -> cadastrar cliente/tenant -> descrever a necessidade -> revisar a
previa -> aprovar -> acompanhar o historico do cliente e a biblioteca.

Por seguranca o servidor escuta em 127.0.0.1 por padrao, exige sessao autenticada
e um cabecalho anti-CSRF nas operacoes de escrita.
"""

import json
import os
import posixpath
import re
import threading
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .errors import DtDashError
from .version import __version__
from .webauth import ADMIN_ROLES, WRITE_ROLES, SessionStore, UserStore

WEBUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webui")
MAX_UPLOAD_BYTES = 32 * 1024 * 1024
COOKIE_NAME = "dtdash_session"
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "dtdash"
FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="7" fill="#1f6feb"/>'
    '<rect x="7" y="8" width="8" height="7" rx="2" fill="#fff"/>'
    '<rect x="17" y="8" width="8" height="12" rx="2" fill="#fff" opacity=".8"/>'
    '<rect x="7" y="17" width="8" height="7" rx="2" fill="#fff" opacity=".8"/>'
    '<rect x="17" y="22" width="8" height="2" rx="1" fill="#fff" opacity=".5"/></svg>'
)


def parse_multipart(payload, content_type):
    """Parser minimo de multipart/form-data (substitui o modulo cgi removido)."""

    match = re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not match:
        raise DtDashError("multipart sem boundary")
    boundary = ("--" + match.group(1)).encode("utf-8")
    out = []
    for chunk in payload.split(boundary):
        if not chunk or chunk in (b"--\r\n", b"--", b"\r\n"):
            continue
        chunk = chunk.lstrip(b"\r\n")
        header_blob, separator, body = chunk.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = header_blob.decode("utf-8", "replace")
        disposition = ""
        for line in headers.splitlines():
            if line.lower().startswith("content-disposition:"):
                disposition = line
                break
        name_match = re.search(r'filename="([^"]*)"', disposition)
        if not name_match or not name_match.group(1):
            continue
        out.append((name_match.group(1), body.rstrip(b"\r\n")))
    return out


class DtDashHandler(BaseHTTPRequestHandler):
    service = None
    users = None
    sessions = None
    token = ""                 # token opcional para automacao (X-Dtdash-Token)
    server_version = "dtdash/%s" % __version__
    _lock = threading.Lock()

    # ------------------------------------------------------------- utilidades
    def log_message(self, fmt, *args):  # pragma: no cover - ruido no console
        pass

    def _send(self, status, body, content_type="application/json; charset=utf-8",
              extra_headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, indent=2)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    def _send_file(self, path, content_type):
        if not os.path.isfile(path):
            return self._send(404, {"error": "arquivo nao encontrado"})
        with open(path, "rb") as handle:
            body = handle.read()
        return self._send(200, body, "%s; charset=utf-8" % content_type)

    # ------------------------------------------------------------- seguranca
    def _cookie_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return ""
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw)
        except cookies.CookieError:  # pragma: no cover
            return ""
        morsel = jar.get(COOKIE_NAME)
        return morsel.value if morsel else ""

    def _session(self):
        if self.token and self.headers.get("X-Dtdash-Token") == self.token:
            return {"user": "automacao", "role": "admin", "fullName": "Automacao"}
        return self.sessions.get(self._cookie_token())

    def _require(self, roles=None):
        session = self._session()
        if not session:
            raise Unauthorized()
        if roles and session.get("role") not in roles:
            raise Forbidden(session.get("role"))
        return session

    def _check_csrf(self):
        if self.headers.get("X-Dtdash-Token") == self.token and self.token:
            return
        if self.headers.get(CSRF_HEADER) != CSRF_VALUE:
            raise DtDashError("requisicao sem o cabecalho anti-CSRF")

    # ------------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = posixpath.normpath(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/favicon.ico":
                return self._send(200, FAVICON, "image/svg+xml")
            if path in ("/login", "/login.html"):
                return self._send_file(os.path.join(WEBUI_DIR, "login.html"), "text/html")
            if path.startswith("/static/"):
                name = os.path.basename(path[len("/static/"):])
                target = os.path.join(WEBUI_DIR, name)
                ctype = ("text/css" if name.endswith(".css")
                         else "application/javascript" if name.endswith(".js")
                         else "text/html")
                return self._send_file(target, ctype)
            if path in ("/", "/index.html"):
                if not self._session():
                    return self._redirect("/login")
                return self._send_file(os.path.join(WEBUI_DIR, "index.html"), "text/html")
            return self._api_get(path, query)
        except Unauthorized:
            return self._send(401, {"error": "sessao expirada ou ausente"})
        except Forbidden as exc:
            return self._send(403, {"error": "permissao insuficiente (papel %s)" % exc.role})
        except DtDashError as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc)})

    def _api_get(self, path, query):
        if path == "/api/me":
            session = self._require()
            return self._send(200, {"user": session.get("user"), "role": session.get("role"),
                                    "fullName": session.get("fullName")})
        self._require()
        if path == "/api/state":
            return self._send(200, self._state())
        if path == "/api/tenants":
            return self._send(200, self.service.tenants())
        if path == "/api/clients":
            return self._send(200, self.service.history.clients())
        if path == "/api/history":
            return self._send(200, self.service.history.list(
                client=(query.get("client") or [None])[0],
                tenant=(query.get("tenant") or [None])[0],
            ))
        if path == "/api/proposals":
            return self._send(200, [p.to_dict() for p in self.service.proposals.list()])
        if path.startswith("/api/proposals/"):
            parts = path.split("/")
            proposal = self.service.proposals.get(parts[3])
            action = parts[4] if len(parts) >= 5 else ""
            if action == "preview":
                return self._send_file(proposal.preview_path(), "text/html")
            if action == "document":
                return self._send(200, proposal.document())
            if action == "spec":
                return self._send(200, proposal.spec().to_dict())
            return self._send(200, proposal.to_dict())
        if path == "/api/templates":
            return self._send(200, self.service.library.entries())
        if path == "/api/template":
            ref = (query.get("ref") or [""])[0]
            return self._send(200, self.service.library.load(ref))
        if path == "/api/knowledge":
            return self._send(200, self.service.knowledge().stats())
        if path == "/api/catalog":
            from . import catalog

            return self._send(200, [
                {"id": b.bp_id, "domain": b.domain, "title": b.title,
                 "visualization": b.visualization, "question": b.question}
                for b in catalog.CATALOG
            ])
        return self._send(404, {"error": "rota nao encontrada"})

    # ------------------------------------------------------------------ POST
    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = posixpath.normpath(parsed.path)
        try:
            if path == "/api/login":
                return self._login()
            self._check_csrf()
            if path == "/api/logout":
                self.sessions.destroy(self._cookie_token())
                return self._send(200, {"ok": True}, extra_headers={
                    "Set-Cookie": "%s=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"
                                  % COOKIE_NAME})
            return self._api_post(path)
        except Unauthorized:
            return self._send(401, {"error": "sessao expirada ou ausente"})
        except Forbidden as exc:
            return self._send(403, {"error": "permissao insuficiente (papel %s)" % exc.role})
        except DtDashError as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc)})

    def _api_post(self, path):
        if path == "/api/plan":
            self._require(WRITE_ROLES)
            return self._send(200, self._plan(self._json_body()))
        if path == "/api/tenants":
            self._require(WRITE_ROLES)
            profile = self.service.upsert_tenant(self._json_body())
            return self._send(200, {"ok": True, "name": profile.name,
                                    "platformUrl": profile.platform_url})
        if path.startswith("/api/tenants/"):
            parts = path.split("/")
            name = urllib.parse.unquote(parts[3])
            action = parts[4] if len(parts) >= 5 else ""
            if action == "delete":
                self._require(ADMIN_ROLES)
                self.service.delete_tenant(name)
                return self._send(200, {"ok": True})
            if action == "test":
                self._require(WRITE_ROLES)
                caps = self.service.capabilities(name, probe=True, cache=False)
                return self._send(200, caps.to_dict())
        if path == "/api/kb/sync":
            self._require(WRITE_ROLES)
            body = self._json_body()
            with self._lock:
                return self._send(200, self.service.sync_knowledge(
                    github=body.get("github", True), docs=body.get("docs", True)))
        if path == "/api/upload":
            self._require(WRITE_ROLES)
            return self._send(200, self._upload())
        if path == "/api/selftest":
            self._require(WRITE_ROLES)
            body = self._json_body()
            report, saved = self.service.selftest(
                tenant=body.get("tenant") or None, write=bool(body.get("write")),
                share=body.get("share", True), cleanup=body.get("cleanup", True),
                queries=body.get("queries", True), metrics=body.get("metrics", True),
            )
            payload = report.to_dict()
            payload["reportPath"] = saved
            return self._send(200, payload)
        if path.startswith("/api/proposals/"):
            parts = path.split("/")
            proposal_id = parts[3]
            action = parts[4] if len(parts) >= 5 else ""
            body = self._json_body()
            if action == "approve":
                session = self._require(WRITE_ROLES)
                return self._send(200, self._approve(proposal_id, body, session))
            if action == "reject":
                self._require(WRITE_ROLES)
                proposal = self.service.reject(proposal_id, body.get("reason", ""))
                return self._send(200, proposal.to_dict())
            if action == "template":
                self._require(WRITE_ROLES)
                saved = self.service.save_as_template(
                    proposal_id, scope=body.get("scope", "library"),
                    client=body.get("client"))
                return self._send(200, {"path": saved})
        return self._send(404, {"error": "rota nao encontrada"})

    # ------------------------------------------------------------------ acoes
    def _login(self):
        body = self._json_body()
        user = self.users.authenticate(body.get("user"), body.get("password"))
        if not user:
            return self._send(401, {"error": "usuario ou senha invalidos"})
        token = self.sessions.create(user)
        cookie = ("%s=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=%d"
                  % (COOKIE_NAME, token, self.sessions.ttl))
        return self._send(200, {"ok": True, "user": self.users.public(user)},
                          extra_headers={"Set-Cookie": cookie})

    def _state(self):
        return {
            "version": __version__,
            "workspace": self.service.workspace.root,
            "tenants": self.service.tenants(),
            "knowledge": self.service.knowledge().stats(),
            "templates": len(self.service.library.entries()),
            "proposals": len(self.service.proposals.ids()),
            "deployments": len(self.service.history.list(limit=1000)),
            "clients": self.service.history.clients(),
        }

    def _plan(self, body):
        description = (body.get("description") or "").strip()
        if not description:
            raise DtDashError("descreva a necessidade do dashboard")
        outcome = self.service.plan(
            description,
            tenant=body.get("tenant") or None,
            name=body.get("name") or None,
            audience=body.get("audience") or None,
            segment_mode=body.get("segmentMode") or "tile",
            max_tiles=int(body["maxTiles"]) if body.get("maxTiles") else None,
            base_template=body.get("base") or None,
            probe=not body.get("offline"),
            validate_live=bool(body.get("validateLive")),
            client_name=body.get("client") or None,
            on_missing=body.get("onMissing") or "drop",
        )
        spec = outcome["spec"]
        report = outcome["report"]
        return {
            "proposalId": outcome["proposal"].proposal_id,
            "previewUrl": "/api/proposals/%s/preview" % outcome["proposal"].proposal_id,
            "name": spec.name,
            "audience": spec.audience,
            "domains": spec.domains,
            "tiles": len(spec.data_tiles()),
            "segments": [s.to_dict() for s in spec.segments],
            "variables": [v.to_dict() for v in spec.variables],
            "warnings": spec.warnings,
            "droppedTiles": spec.dropped_tiles,
            "metricsSummary": spec.metrics_summary,
            "capabilities": spec.capabilities,
            "report": report.to_dict(),
            "text": outcome["text"],
        }

    def _approve(self, proposal_id, body, session):
        outcome = self.service.approve(
            proposal_id,
            tenant=body.get("tenant") or None,
            share=bool(body.get("share")),
            save_template=not body.get("noTemplate"),
            scope=body.get("scope", "clients"),
            force=bool(body.get("force")),
            dry_run=bool(body.get("dryRun")),
            client_name=body.get("client") or None,
            user=session.get("user", ""),
        )
        result = outcome["result"].to_dict()
        result["proposalId"] = outcome["proposal"].proposal_id
        result["history"] = outcome.get("history")
        return result

    def _upload(self):
        content_type = self.headers.get("Content-Type") or ""
        if "multipart/form-data" not in content_type:
            raise DtDashError("envie os arquivos como multipart/form-data")
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise DtDashError("upload vazio")
        if length > MAX_UPLOAD_BYTES:
            raise DtDashError("upload maior que %d MB" % (MAX_UPLOAD_BYTES // (1024 * 1024)))
        parts = parse_multipart(self.rfile.read(length), content_type)

        from .knowledge import KnowledgeSync

        sync = KnowledgeSync(self.service.workspace)
        saved = [sync.add_upload(filename, data) for filename, data in parts]
        if not saved:
            raise DtDashError("nenhum arquivo recebido")
        self.service.knowledge(rebuild=True)
        return {"saved": saved, "knowledge": self.service.knowledge().stats()}


class Unauthorized(Exception):
    pass


class Forbidden(Exception):
    def __init__(self, role=""):
        super().__init__(role)
        self.role = role or "?"


def serve(service, host="127.0.0.1", port=8080, users=None, sessions=None):
    users = users or UserStore(service.workspace)
    bootstrap = None
    if users.empty():
        bootstrap = users.bootstrap_admin()

    DtDashHandler.service = service
    DtDashHandler.users = users
    DtDashHandler.sessions = sessions or SessionStore()
    DtDashHandler.token = os.environ.get("DTDASH_WEB_TOKEN", "")

    httpd = ThreadingHTTPServer((host, port), DtDashHandler)
    url = "http://%s:%d/" % (host, port)
    print("dtdash %s - interface web em %s" % (__version__, url))
    if bootstrap:
        print("")
        print("  Primeiro acesso criado:")
        print("    usuario: %s" % bootstrap[0])
        print("    senha .: %s" % bootstrap[1])
        print("  Anote agora - a senha nao sera exibida novamente.")
        print("  Troque com: dtdash users passwd %s" % bootstrap[0])
        print("")
    if host not in ("127.0.0.1", "localhost"):
        print("ATENCAO: servidor exposto fora do localhost. Use HTTPS por um proxy reverso.")
    print("Ctrl+C para encerrar.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        print("\nencerrando...")
    finally:
        httpd.server_close()
