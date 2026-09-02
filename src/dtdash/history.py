"""Historico de dashboards publicados por cliente/tenant."""

import json
import os
import time

HISTORY_FILE = "history.json"


class DeploymentHistory(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.path = os.path.join(workspace.state_dir, HISTORY_FILE)

    def _read(self):
        if not os.path.isfile(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return []
        return payload.get("deployments") or []

    def _write(self, entries):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"deployments": entries}, handle, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------- api
    def record(self, spec, result, proposal_id="", user="", dry_run=False):
        entries = self._read()
        entry = {
            "id": "%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), spec.slug[:40]),
            "at": time.time(),
            "when": time.strftime("%Y-%m-%d %H:%M:%S"),
            "client": spec.client_name or spec.tenant,
            "tenant": spec.tenant,
            "name": spec.name,
            "documentId": result.document_id,
            "url": result.url,
            "tiles": len(spec.data_tiles()),
            "segments": [{"name": s.name, "uid": s.uid} for s in spec.segments],
            "templatePath": result.template_path,
            "proposalId": proposal_id,
            "audience": spec.audience,
            "domains": spec.domains,
            "user": user,
            "dryRun": bool(dry_run),
            "shared": result.shared,
            "warnings": list(result.warnings),
        }
        entries.insert(0, entry)
        self._write(entries[:2000])
        return entry

    def list(self, client=None, tenant=None, limit=200):
        entries = self._read()
        if client:
            entries = [e for e in entries if (e.get("client") or "").lower() == client.lower()]
        if tenant:
            entries = [e for e in entries if e.get("tenant") == tenant]
        return entries[:limit]

    def clients(self):
        """Resumo por cliente para a tela principal."""

        summary = {}
        for entry in self._read():
            if entry.get("dryRun"):
                continue
            key = entry.get("client") or entry.get("tenant") or "-"
            item = summary.setdefault(key, {"client": key, "dashboards": 0, "last": "",
                                            "tenants": set()})
            item["dashboards"] += 1
            item["tenants"].add(entry.get("tenant") or "")
            if not item["last"]:
                item["last"] = entry.get("when") or ""
        out = []
        for item in summary.values():
            item["tenants"] = sorted(t for t in item["tenants"] if t)
            out.append(item)
        return sorted(out, key=lambda i: i["client"].lower())
