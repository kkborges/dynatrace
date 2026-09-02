"""Interface web do dtdash (servidor da biblioteca padrao).

Fluxo: descrever -> gerar previa -> revisar -> aprovar -> criar no tenant.
Por seguranca o servidor escuta em 127.0.0.1 por padrao; defina
``DTDASH_WEB_TOKEN`` para exigir um token quando publicar em outra interface.
"""

import json
import os
import posixpath
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .errors import DtDashError
from .version import __version__

WEBUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webui")
MAX_UPLOAD_BYTES = 32 * 1024 * 1024


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
        header_blob, _, body = chunk.partition(b"\r\n\r\n")
        if not _:
            continue
        headers = header_blob.decode("utf-8", "replace")
        disposition = ""
        for line in headers.splitlines():
            if line.lower().startswith("content-disposition:"):
                disposition = line
                break
        filename = ""
        name_match = re.search(r'filename="([^"]*)"', disposition)
        if name_match:
            filename = name_match.group(1)
        if not filename:
            continue
        out.append((filename, body.rstrip(b"\r\n")))
    return out


class DtDashHandler(BaseHTTPRequestHandler):
    service = None
    token = ""
    server_version = "dtdash/%s" % __version__
    _lock = threading.Lock()

    # ------------------------------------------------------------- utilidades
    def log_message(self, fmt, *args):  # pragma: no cover - ruido no console
        pass

    def _authorized(self):
        if not self.token:
            return True
        provided = self.headers.get("X-Dtdash-Token") or urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        ).get("token", [""])[0]
        return provided == self.token

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, indent=2)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {}

    # ------------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        if not self._authorized():
            return self._send(401, {"error": "token invalido"})
        parsed = urllib.parse.urlparse(self.path)
        path = posixpath.normpath(parsed.path)
        try:
            if path in ("/", "/index.html"):
                return self._send_file(os.path.join(WEBUI_DIR, "index.html"), "text/html")
            if path.startswith("/static/"):
                name = path[len("/static/"):]
                target = os.path.join(WEBUI_DIR, os.path.basename(name))
                if not os.path.isfile(target):
                    return self._send(404, {"error": "nao encontrado"})
                ctype = "text/css" if name.endswith(".css") else "application/javascript"
                return self._send_file(target, ctype)
            if path == "/api/state":
                return self._send(200, self._state())
            if path == "/api/proposals":
                return self._send(200, [p.to_dict() for p in self.service.proposals.list()])
            if path.startswith("/api/proposals/"):
                parts = path.split("/")
                proposal = self.service.proposals.get(parts[3])
                if len(parts) >= 5 and parts[4] == "preview":
                    return self._send_file(proposal.preview_path(), "text/html")
                if len(parts) >= 5 and parts[4] == "document":
                    return self._send(200, proposal.document())
                if len(parts) >= 5 and parts[4] == "spec":
                    return self._send(200, proposal.spec().to_dict())
                return self._send(200, proposal.to_dict())
            if path == "/api/templates":
                return self._send(200, self.service.library.entries())
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
        except DtDashError as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc)})

    def _send_file(self, path, content_type):
        if not os.path.isfile(path):
            return self._send(404, {"error": "arquivo nao encontrado"})
        with open(path, "rb") as handle:
            body = handle.read()
        return self._send(200, body, "%s; charset=utf-8" % content_type)

    # ------------------------------------------------------------------ POST
    def do_POST(self):  # noqa: N802
        if not self._authorized():
            return self._send(401, {"error": "token invalido"})
        parsed = urllib.parse.urlparse(self.path)
        path = posixpath.normpath(parsed.path)
        try:
            if path == "/api/plan":
                return self._send(200, self._plan(self._json_body()))
            if path == "/api/kb/sync":
                body = self._json_body()
                with self._lock:
                    return self._send(200, self.service.sync_knowledge(
                        github=body.get("github", True), docs=body.get("docs", True)
                    ))
            if path == "/api/upload":
                return self._send(200, self._upload())
            if path == "/api/selftest":
                body = self._json_body()
                report, saved = self.service.selftest(
                    tenant=body.get("tenant") or None,
                    write=bool(body.get("write")),
                    share=body.get("share", True),
                    cleanup=body.get("cleanup", True),
                    queries=body.get("queries", True),
                    metrics=body.get("metrics", True),
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
                    return self._send(200, self._approve(proposal_id, body))
                if action == "reject":
                    proposal = self.service.reject(proposal_id, body.get("reason", ""))
                    return self._send(200, proposal.to_dict())
                if action == "template":
                    path_saved = self.service.save_as_template(
                        proposal_id, scope=body.get("scope", "library"),
                        client=body.get("client"),
                    )
                    return self._send(200, {"path": path_saved})
            return self._send(404, {"error": "rota nao encontrada"})
        except DtDashError as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc)})

    # ------------------------------------------------------------------ acoes
    def _state(self):
        config = self.service.config
        tenants = []
        for name in config.tenant_names():
            profile = config.get_tenant(name)
            tenants.append({
                "name": name,
                "platformUrl": profile.platform_url,
                "client": profile.client_name,
                "hasCredentials": profile.has_credentials(),
                "default": config.setting("default_tenant") == name,
            })
        return {
            "version": __version__,
            "workspace": self.service.workspace.root,
            "tenants": tenants,
            "knowledge": self.service.knowledge().stats(),
            "templates": len(self.service.library.entries()),
            "proposals": len(self.service.proposals.ids()),
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
            "report": report.to_dict(),
            "text": outcome["text"],
        }

    def _approve(self, proposal_id, body):
        outcome = self.service.approve(
            proposal_id,
            tenant=body.get("tenant") or None,
            share=bool(body.get("share")),
            save_template=not body.get("noTemplate"),
            scope=body.get("scope", "clients"),
            force=bool(body.get("force")),
            dry_run=bool(body.get("dryRun")),
            client_name=body.get("client") or None,
            on_missing=body.get("onMissing") or "drop",
        )
        result = outcome["result"].to_dict()
        result["proposalId"] = outcome["proposal"].proposal_id
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
        payload = self.rfile.read(length)
        parts = parse_multipart(payload, content_type)

        from .knowledge import KnowledgeSync

        sync = KnowledgeSync(self.service.workspace)
        saved = []
        for filename, data in parts:
            if not filename:
                continue
            saved.append(sync.add_upload(filename, data))
        if not saved:
            raise DtDashError("nenhum arquivo recebido")
        self.service.knowledge(rebuild=True)
        return {"saved": saved, "knowledge": self.service.knowledge().stats()}


def serve(service, host="127.0.0.1", port=8080):
    DtDashHandler.service = service
    DtDashHandler.token = os.environ.get("DTDASH_WEB_TOKEN", "")
    httpd = ThreadingHTTPServer((host, port), DtDashHandler)
    url = "http://%s:%d/" % (host, port)
    print("dtdash %s - interface web em %s" % (__version__, url))
    if host not in ("127.0.0.1", "localhost") and not DtDashHandler.token:
        print("ATENCAO: servidor exposto sem token. Defina DTDASH_WEB_TOKEN.")
    print("Ctrl+C para encerrar.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        print("\nencerrando...")
    finally:
        httpd.server_close()
