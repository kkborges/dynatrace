"""Publicacao no tenant: segments, dashboard e registro do template."""

import time

from .builder import build_dashboard
from .errors import ApiError, ValidationError
from .library import SCOPE_CLIENT, TemplateLibrary
from .validator import validate_spec


class DeployResult(object):
    def __init__(self):
        self.document_id = ""
        self.url = ""
        self.segments = []          # [{"key","name","uid","created"}]
        self.template_path = ""
        self.shared = False
        self.warnings = []
        self.started_at = time.time()

    def to_dict(self):
        return {
            "documentId": self.document_id,
            "url": self.url,
            "segments": self.segments,
            "templatePath": self.template_path,
            "shared": self.shared,
            "warnings": self.warnings,
            "durationSeconds": round(time.time() - self.started_at, 2),
        }


class Deployer(object):
    def __init__(self, client, workspace, library=None):
        self.client = client
        self.workspace = workspace
        self.library = library or TemplateLibrary(workspace)

    # ------------------------------------------------------------- segments
    def ensure_segments(self, spec, dry_run=False):
        """Cria (ou reaproveita) os filter-segments do spec. Retorna key -> uid."""

        mapping = {}
        outcome = []
        existing = {}
        if spec.segments and not dry_run:
            try:
                for segment in self.client.list_segments():
                    name = (segment.get("name") or "").strip().lower()
                    uid = segment.get("uid") or segment.get("id")
                    if name and uid:
                        existing[name] = uid
            except ApiError as exc:
                outcome.append({"key": "-", "name": "-", "uid": "",
                                "created": False, "error": str(exc)})

        for segment in spec.segments:
            key_name = segment.name.strip().lower()
            if key_name in existing:
                segment.uid = existing[key_name]
                mapping[segment.key] = segment.uid
                outcome.append({"key": segment.key, "name": segment.name,
                                "uid": segment.uid, "created": False})
                continue
            if dry_run:
                outcome.append({"key": segment.key, "name": segment.name,
                                "uid": "(dry-run)", "created": False})
                continue
            try:
                created = self.client.create_segment(segment.api_payload())
            except ApiError as exc:
                outcome.append({"key": segment.key, "name": segment.name, "uid": "",
                                "created": False, "error": str(exc)})
                continue
            uid = created.get("uid") or created.get("id") or ""
            segment.uid = uid
            if uid:
                mapping[segment.key] = uid
            outcome.append({"key": segment.key, "name": segment.name, "uid": uid,
                            "created": True})
        return mapping, outcome

    # ------------------------------------------------------------ dashboard
    def deploy(self, spec, share=False, save_template=True,
               scope=SCOPE_CLIENT, force=False, dry_run=False):
        result = DeployResult()

        segment_uids, result.segments = self.ensure_segments(spec, dry_run=dry_run)
        missing = [s for s in spec.segments if not s.uid and not dry_run]
        if missing:
            result.warnings.append(
                "segments nao criados: %s (o dashboard sera publicado sem eles)"
                % ", ".join(s.name for s in missing)
            )

        document = build_dashboard(spec, segment_uids=segment_uids)
        report = validate_spec(spec, document)
        if report.errors and not force:
            raise ValidationError(
                "dashboard invalido (%d erro(s)): %s"
                % (len(report.errors), "; ".join(f.message for f in report.errors[:5]))
            )
        if report.errors:
            result.warnings.append(
                "publicado com %d erro(s) de validacao ignorados (--force)" % len(report.errors)
            )

        if dry_run:
            result.document_id = "(dry-run)"
            result.url = "(dry-run)"
            return result, document, report

        created = self.client.create_document(
            name=spec.name,
            content=document["content"],
            doc_type="dashboard",
            description=spec.description,
            is_private=False,
        )
        result.document_id = created.get("id") or created.get("documentId") or ""
        if not result.document_id:
            raise ApiError("a API nao retornou o id do documento criado")
        result.url = self.client.profile.dashboard_url(result.document_id)

        if share:
            try:
                self.client.share_document_with_environment(result.document_id)
                result.shared = True
            except ApiError as exc:
                result.warnings.append("nao foi possivel compartilhar: %s" % exc)

        if save_template:
            deployment = {
                "documentId": result.document_id,
                "url": result.url,
                "tenant": spec.tenant,
                "environmentId": self.client.profile.environment_id,
                "deployedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "segments": [
                    {"name": s.name, "uid": s.uid} for s in spec.segments if s.uid
                ],
            }
            result.template_path = self.library.save(
                document,
                spec=spec,
                scope=scope,
                client=spec.client_name or spec.tenant,
                deployment=deployment,
                origin="cliente" if scope == SCOPE_CLIENT else "biblioteca",
            )
        return result, document, report
