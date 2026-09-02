"""Persistencia das propostas (previa aguardando aprovacao)."""

import json
import os
import time

from .errors import NotFoundError
from .spec import DashboardSpec, slugify

STATUS_PENDING = "pendente"
STATUS_APPROVED = "aprovado"
STATUS_REJECTED = "rejeitado"
STATUS_DEPLOYED = "publicado"


class Proposal(object):
    def __init__(self, workspace, proposal_id, meta=None):
        self.workspace = workspace
        self.proposal_id = proposal_id
        self.meta = meta or {}

    # ------------------------------------------------------------- caminhos
    @property
    def path(self):
        return os.path.join(self.workspace.proposals_dir, self.proposal_id)

    def file(self, name):
        return os.path.join(self.path, name)

    # ------------------------------------------------------------- conteudo
    def spec(self):
        with open(self.file("spec.json"), "r", encoding="utf-8") as handle:
            return DashboardSpec.from_dict(json.load(handle))

    def document(self):
        with open(self.file("dashboard.json"), "r", encoding="utf-8") as handle:
            return json.load(handle)

    def report(self):
        path = self.file("report.json")
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def preview_path(self):
        return self.file("preview.html")

    def status(self):
        return self.meta.get("status", STATUS_PENDING)

    def set_status(self, status, **extra):
        self.meta["status"] = status
        self.meta["updatedAt"] = time.time()
        self.meta.update(extra)
        self._write_meta()
        return self

    def _write_meta(self):
        with open(self.file("meta.json"), "w", encoding="utf-8") as handle:
            json.dump(self.meta, handle, ensure_ascii=False, indent=2)

    def to_dict(self):
        data = dict(self.meta)
        data["id"] = self.proposal_id
        data["path"] = self.path
        return data


class ProposalStore(object):
    def __init__(self, workspace):
        self.workspace = workspace

    def new_id(self, spec):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return "%s-%s" % (stamp, slugify(spec.name, 40))

    def create(self, spec, document, report=None, preview_html=None, extra_meta=None):
        self.workspace.ensure()
        proposal_id = self.new_id(spec)
        proposal = Proposal(self.workspace, proposal_id)
        os.makedirs(proposal.path, exist_ok=True)

        with open(proposal.file("spec.json"), "w", encoding="utf-8") as handle:
            json.dump(spec.to_dict(), handle, ensure_ascii=False, indent=2)
        with open(proposal.file("dashboard.json"), "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
        if report is not None:
            with open(proposal.file("report.json"), "w", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2)
        if preview_html:
            with open(proposal.preview_path(), "w", encoding="utf-8") as handle:
                handle.write(preview_html)

        proposal.meta = {
            "id": proposal_id,
            "name": spec.name,
            "tenant": spec.tenant,
            "client": spec.client_name,
            "audience": spec.audience,
            "domains": spec.domains,
            "tiles": len(spec.data_tiles()),
            "segments": [s.name for s in spec.segments],
            "status": STATUS_PENDING,
            "createdAt": time.time(),
        }
        proposal.meta.update(extra_meta or {})
        proposal._write_meta()
        return proposal

    def get(self, proposal_id):
        path = os.path.join(self.workspace.proposals_dir, proposal_id)
        if not os.path.isdir(path):
            match = [p for p in self.ids() if p.endswith(proposal_id) or proposal_id in p]
            if len(match) == 1:
                proposal_id = match[0]
                path = os.path.join(self.workspace.proposals_dir, proposal_id)
            else:
                raise NotFoundError("proposta '%s' nao encontrada" % proposal_id)
        meta = {}
        meta_path = os.path.join(path, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as handle:
                meta = json.load(handle)
        return Proposal(self.workspace, proposal_id, meta)

    def ids(self):
        root = self.workspace.proposals_dir
        if not os.path.isdir(root):
            return []
        return sorted(
            [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))],
            reverse=True,
        )

    def list(self, limit=50):
        out = []
        for proposal_id in self.ids()[:limit]:
            try:
                out.append(self.get(proposal_id))
            except NotFoundError:  # pragma: no cover
                continue
        return out

    def latest(self):
        ids = self.ids()
        if not ids:
            raise NotFoundError("nenhuma proposta encontrada")
        return self.get(ids[0])
