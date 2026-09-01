"""Biblioteca de templates de dashboard (genericos e criados em clientes)."""

import json
import os
import time

from .errors import NotFoundError
from .spec import slugify

SCOPE_LIBRARY = "library"
SCOPE_CLIENT = "clients"
METADATA_KEY = "dtdash"


class TemplateLibrary(object):
    def __init__(self, workspace):
        self.workspace = workspace

    # ------------------------------------------------------------- caminhos
    def scope_dir(self, scope):
        return {
            SCOPE_LIBRARY: self.workspace.library_dir,
            SCOPE_CLIENT: self.workspace.clients_dir,
        }.get(scope, self.workspace.library_dir)

    # -------------------------------------------------------------- gravacao
    def save(self, document, spec=None, scope=SCOPE_CLIENT, client=None, deployment=None,
             origin="dtdash", overwrite=True):
        """Grava o dashboard como template reutilizavel.

        Dashboards criados em clientes vao para ``dashboards/clients/<cliente>/`` e
        carregam metadados de origem para permitir reuso em outros clientes.
        """

        self.workspace.ensure()
        client_slug = slugify(client or (spec.client_name if spec else "") or "generico", 50)
        name = document.get("name") or (spec.name if spec else "dashboard")
        slug = slugify(name, 60)

        if scope == SCOPE_CLIENT:
            folder = os.path.join(self.workspace.clients_dir, client_slug)
        else:
            folder = self.workspace.library_dir
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "%s.json" % slug)
        if os.path.exists(path) and not overwrite:
            path = os.path.join(folder, "%s-%s.json" % (slug, time.strftime("%Y%m%d%H%M%S")))

        payload = dict(document)
        payload[METADATA_KEY] = self._metadata(spec, scope, client_slug, deployment, origin)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        self.reindex()
        return path

    def _metadata(self, spec, scope, client_slug, deployment, origin):
        meta = {
            "origin": origin,
            "scope": scope,
            "client": client_slug,
            "savedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "reusable": True,
        }
        if spec is not None:
            meta.update(
                {
                    "audience": spec.audience,
                    "domains": spec.domains,
                    "tags": spec.tags,
                    "tenant": spec.tenant,
                    "requestText": spec.request_text[:2000],
                    "requirements": [r.text for r in spec.requirements],
                    "segments": [s.to_dict() for s in spec.segments],
                    "dataObjects": sorted(
                        {t.domain for t in spec.tiles if t.domain}
                    ),
                }
            )
        if deployment:
            meta["deployment"] = deployment
        return meta

    # -------------------------------------------------------------- leitura
    def entries(self, scope=None, client=None):
        out = []
        scopes = [scope] if scope else [SCOPE_LIBRARY, SCOPE_CLIENT]
        for current in scopes:
            root = self.scope_dir(current)
            if not os.path.isdir(root):
                continue
            for base, _dirs, files in os.walk(root):
                for filename in sorted(files):
                    if not filename.endswith(".json") or filename == "index.json":
                        continue
                    path = os.path.join(base, filename)
                    entry = self._read_entry(path, current)
                    if entry is None:
                        continue
                    if client and entry.get("client") != slugify(client, 50):
                        continue
                    out.append(entry)
        return sorted(out, key=lambda e: (e.get("scope", ""), e.get("name", "")))

    def _read_entry(self, path, scope):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        content = payload.get("content") if isinstance(payload.get("content"), dict) else payload
        if not isinstance(content.get("tiles"), dict):
            return None
        meta = payload.get(METADATA_KEY) or {}
        rel = os.path.relpath(path, self.workspace.root)
        return {
            "ref": rel.replace(os.sep, "/"),
            "path": path,
            "name": payload.get("name") or os.path.basename(path),
            "scope": meta.get("scope", scope),
            "client": meta.get("client", ""),
            "audience": meta.get("audience", ""),
            "domains": meta.get("domains", []),
            "tags": meta.get("tags", []),
            "tiles": len(content.get("tiles") or {}),
            "variables": len(content.get("variables") or []),
            "segments": [s.get("name") for s in meta.get("segments", []) if isinstance(s, dict)],
            "savedAt": meta.get("savedAt", ""),
            "tenant": meta.get("tenant", ""),
            "requirements": meta.get("requirements", []),
            "deployment": meta.get("deployment", {}),
        }

    def load(self, ref):
        """Carrega um template pelo caminho relativo, absoluto ou por nome."""

        candidates = [ref, os.path.join(self.workspace.root, ref)]
        for candidate in candidates:
            if os.path.isfile(candidate):
                with open(candidate, "r", encoding="utf-8") as handle:
                    return json.load(handle)
        wanted = slugify(ref, 60)
        for entry in self.entries():
            if slugify(entry["name"], 60) == wanted or entry["ref"].endswith("/%s.json" % wanted):
                with open(entry["path"], "r", encoding="utf-8") as handle:
                    return json.load(handle)
        raise NotFoundError("template '%s' nao encontrado" % ref)

    def search(self, text, limit=5):
        """Busca simples por palavras nos metadados dos templates."""

        words = [w for w in slugify(text, 200).split("-") if len(w) > 3]
        scored = []
        for entry in self.entries():
            haystack = slugify(
                " ".join(
                    [entry["name"], " ".join(entry.get("domains") or []),
                     " ".join(entry.get("tags") or []),
                     " ".join(entry.get("requirements") or [])]
                ),
                4000,
            )
            score = sum(1 for w in words if w in haystack)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda item: -item[0])
        return [entry for _, entry in scored[:limit]]

    # -------------------------------------------------------------- indices
    def reindex(self):
        entries = self.entries()
        path = os.path.join(self.workspace.dashboards_dir, "index.json")
        os.makedirs(self.workspace.dashboards_dir, exist_ok=True)
        payload = {
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total": len(entries),
            "templates": [
                {k: v for k, v in entry.items() if k != "path"} for entry in entries
            ],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return path
