"""Camada de servico compartilhada entre a CLI e a interface web."""

import json
import os
import time

from .builder import build_dashboard, dashboard_to_spec
from .capabilities import TenantCapabilities
from .client import DynatraceClient
from .config import Config, Workspace
from .deploy import Deployer
from .errors import ConfigError, DtDashError
from .knowledge import KnowledgeStore, KnowledgeSync
from .library import SCOPE_CLIENT, TemplateLibrary
from .planner import Planner
from .preview import render_html, render_text
from .proposals import ProposalStore, STATUS_APPROVED, STATUS_DEPLOYED, STATUS_REJECTED
from .selftest import SelfTest
from .validator import validate_queries_live, validate_spec


class DashboardService(object):
    def __init__(self, workspace=None, config=None):
        self.workspace = workspace or Workspace()
        self.config = config or Config.load(self.workspace)
        self.proposals = ProposalStore(self.workspace)
        self.library = TemplateLibrary(self.workspace)
        self._knowledge = None
        self._clients = {}

    # ------------------------------------------------------------ conhecimento
    def knowledge(self, rebuild=False):
        if self._knowledge is None or rebuild:
            self._knowledge = KnowledgeStore(self.workspace).build()
        return self._knowledge

    def sync_knowledge(self, github=True, docs=True, only=None):
        sync = KnowledgeSync(self.workspace)
        out = {}
        if github:
            out["github"] = sync.sync_github(only=only).to_dict()
        if docs:
            out["docs"] = sync.sync_docs(only=only).to_dict()
        self.knowledge(rebuild=True)
        out["index"] = self.knowledge().stats()
        return out

    # ----------------------------------------------------------------- tenant
    def tenant(self, name=None, required=True):
        try:
            return self.config.get_tenant(name)
        except ConfigError:
            if required:
                raise
            return None

    def client_for(self, name=None):
        profile = self.tenant(name, required=True)
        profile.validate()
        if profile.name not in self._clients:
            self._clients[profile.name] = DynatraceClient(profile)
        return self._clients[profile.name]

    def capabilities(self, tenant=None, probe=True, cache=True):
        """Descobre o que o tenant oferece (Grail, data objects, DPS)."""

        profile = self.tenant(tenant, required=False)
        if not profile or not probe:
            return TenantCapabilities.offline(profile.environment_id if profile else "")
        cache_path = os.path.join(
            self.workspace.state_dir, "caps-%s.json" % profile.name
        )
        if cache and os.path.isfile(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as handle:
                    return TenantCapabilities.from_dict(json.load(handle))
            except (OSError, ValueError):
                pass
        try:
            client = self.client_for(profile.name)
            caps = TenantCapabilities.probe(client)
        except DtDashError as exc:
            caps = TenantCapabilities.offline(profile.environment_id)
            caps.errors.append(str(exc))
            return caps
        os.makedirs(self.workspace.state_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(caps.to_dict(), handle, ensure_ascii=False, indent=2)
        return caps

    # ------------------------------------------------------------------ plano
    def plan(self, text, tenant=None, name=None, audience=None, segment_mode="tile",
             max_tiles=None, base_template=None, probe=True, validate_live=False,
             client_name=None, extra_domains=None, on_missing="drop"):
        profile = self.tenant(tenant, required=False)
        caps = self.capabilities(tenant, probe=probe)
        dt_client = None
        if caps.online:
            try:
                dt_client = self.client_for(profile.name)
            except DtDashError:
                dt_client = None

        base_spec = None
        if base_template:
            base_spec = dashboard_to_spec(self.library.load(base_template))

        planner = Planner(knowledge=self.knowledge(), client=dt_client, capabilities=caps)
        spec = planner.plan(
            text,
            name=name,
            tenant=profile.name if profile else "",
            client_name=client_name or (profile.client_name if profile else ""),
            segment_mode=segment_mode,
            max_tiles=max_tiles,
            audience=audience,
            base_spec=base_spec,
            extra_domains=extra_domains,
            on_missing=on_missing,
        )
        # sugestoes de templates ja existentes (reuso entre clientes)
        suggestions = self.library.search(text, limit=5)
        if suggestions and not base_template:
            spec.warnings.append(
                "Templates existentes que podem servir de base: %s"
                % ", ".join("%s (%s)" % (s["name"], s["ref"]) for s in suggestions)
            )

        document = build_dashboard(spec)
        report = validate_spec(spec, document)
        if validate_live and dt_client is not None:
            report.query_results = validate_queries_live(spec, dt_client)
            for entry in report.query_results:
                if entry.get("status") in ("invalid", "error"):
                    report.add(
                        "error" if entry.get("status") == "invalid" else "warning",
                        "DQL rejeitada pelo tenant: %s"
                        % (entry.get("message")
                           or _first_notification(entry)
                           or "sem detalhe"),
                        tile=entry.get("tile"), rule="dql-live",
                    )
        preview_html = render_html(spec, report, document)
        proposal = self.proposals.create(
            spec, document, report=report.to_dict(), preview_html=preview_html,
            extra_meta={"suggestions": [s["ref"] for s in suggestions]},
        )
        return {
            "proposal": proposal,
            "spec": spec,
            "document": document,
            "report": report,
            "preview": preview_html,
            "text": render_text(spec, report),
        }

    # -------------------------------------------------------------- aprovacao
    def approve(self, proposal_id=None, tenant=None, share=False, save_template=True,
                scope=SCOPE_CLIENT, force=False, dry_run=False, client_name=None):
        proposal = (
            self.proposals.get(proposal_id) if proposal_id else self.proposals.latest()
        )
        spec = proposal.spec()
        if client_name:
            spec.client_name = client_name
        target = tenant or spec.tenant or None
        dt_client = self.client_for(target)
        spec.tenant = dt_client.profile.name
        if not spec.client_name:
            spec.client_name = dt_client.profile.client_name

        deployer = Deployer(dt_client, self.workspace, self.library)
        result, document, report = deployer.deploy(
            spec, share=share, save_template=save_template, scope=scope,
            force=force, dry_run=dry_run,
        )
        preview_html = render_html(spec, report, document, deployment=result.to_dict())
        with open(proposal.preview_path(), "w", encoding="utf-8") as handle:
            handle.write(preview_html)
        with open(proposal.file("dashboard.json"), "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
        with open(proposal.file("spec.json"), "w", encoding="utf-8") as handle:
            json.dump(spec.to_dict(), handle, ensure_ascii=False, indent=2)
        with open(proposal.file("deployment.json"), "w", encoding="utf-8") as handle:
            json.dump(result.to_dict(), handle, ensure_ascii=False, indent=2)
        proposal.set_status(
            STATUS_DEPLOYED if not dry_run else STATUS_APPROVED,
            documentId=result.document_id,
            url=result.url,
            templatePath=result.template_path,
        )
        return {"proposal": proposal, "result": result, "document": document,
                "report": report, "spec": spec}

    def reject(self, proposal_id=None, reason=""):
        proposal = (
            self.proposals.get(proposal_id) if proposal_id else self.proposals.latest()
        )
        proposal.set_status(STATUS_REJECTED, reason=reason)
        return proposal

    # --------------------------------------------------------------- selftest
    def selftest(self, tenant=None, write=False, share=True, cleanup=True,
                 queries=True, metrics=True, save=True):
        """Roda a bateria de verificacao contra o tenant e guarda o relatorio."""

        client = self.client_for(tenant)
        report = SelfTest(client).run(
            write=write, share=share, cleanup=cleanup, queries=queries, metrics=metrics
        )
        path = ""
        if save:
            os.makedirs(self.workspace.state_dir, exist_ok=True)
            path = os.path.join(
                self.workspace.state_dir,
                "selftest-%s-%s.json" % (client.profile.name,
                                         time.strftime("%Y%m%d-%H%M%S")),
            )
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2)
        return report, path

    # -------------------------------------------------------------- templates
    def save_as_template(self, proposal_id=None, scope="library", client=None):
        proposal = (
            self.proposals.get(proposal_id) if proposal_id else self.proposals.latest()
        )
        spec = proposal.spec()
        return self.library.save(
            proposal.document(), spec=spec, scope=scope, client=client or spec.client_name,
            origin="biblioteca" if scope == "library" else "cliente",
        )


def _first_notification(entry):
    for notification in entry.get("notifications") or []:
        if notification.get("message"):
            return notification["message"]
    return ""
