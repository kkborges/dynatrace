import io
import json
import os
import unittest
from contextlib import redirect_stdout

from tests.helpers import FakeTransport, TempWorkspaceTest

from dtdash import cli
from dtdash.builder import build_dashboard
from dtdash.client import DynatraceClient
from dtdash.errors import NotFoundError
from dtdash.knowledge.sources import KnowledgeSync, html_to_text, _match
from dtdash.knowledge.store import KnowledgeStore
from dtdash.library import TemplateLibrary
from dtdash.planner import Planner
from dtdash.server import parse_multipart
from dtdash.service import DashboardService
from dtdash.httpclient import encode_multipart


class LibraryTest(TempWorkspaceTest):
    def setUp(self):
        super().setUp()
        self.library = TemplateLibrary(self.workspace)
        self.spec = Planner(knowledge=KnowledgeStore(self.workspace).build()).plan(
            "saude dos servicos com taxa de erro e latencia"
        )
        self.spec.client_name = "acme"
        self.document = build_dashboard(self.spec)

    def test_salva_template_de_cliente_com_metadados(self):
        path = self.library.save(self.document, spec=self.spec, scope="clients", client="Acme S.A.",
                                 deployment={"documentId": "doc-1"})
        self.assertTrue(os.path.isfile(path))
        self.assertIn(os.path.join("clients", "acme-s-a"), path)
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["dtdash"]["scope"], "clients")
        self.assertEqual(payload["dtdash"]["deployment"]["documentId"], "doc-1")
        self.assertTrue(payload["dtdash"]["reusable"])
        self.assertIn("content", payload)

    def test_lista_e_carrega_templates(self):
        self.library.save(self.document, spec=self.spec, scope="library")
        entries = self.library.entries()
        self.assertEqual(len(entries), 1)
        loaded = self.library.load(entries[0]["ref"])
        self.assertEqual(loaded["name"], self.document["name"])

    def test_busca_por_palavra(self):
        self.library.save(self.document, spec=self.spec, scope="library")
        self.assertTrue(self.library.search("servicos latencia"))
        self.assertFalse(self.library.search("assunto totalmente diferente xyz"))

    def test_indice_e_gerado(self):
        self.library.save(self.document, spec=self.spec, scope="library")
        index = os.path.join(self.workspace.dashboards_dir, "index.json")
        self.assertTrue(os.path.isfile(index))
        with open(index, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["total"], 1)

    def test_template_inexistente(self):
        self.assertRaises(NotFoundError, self.library.load, "nao-existe")


class KnowledgeTest(TempWorkspaceTest):
    def test_indexa_e_busca_a_semente(self):
        store = KnowledgeStore(self.workspace).build()
        self.assertGreaterEqual(store.stats()["documents"], 5)
        hits = store.search("como aplicar segments no dashboard")
        self.assertTrue(hits)
        self.assertTrue(any("segment" in hit.doc.title.lower() for hit in hits))

    def test_classifica_dashboard_json(self):
        path = os.path.join(self.workspace.examples_dir, "exemplo.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"name": "Exemplo", "content": {"version": 21, "tiles": {
                "1": {"type": "markdown", "content": "# oi"}}, "layouts": {}}}, handle)
        store = KnowledgeStore(self.workspace).build()
        dashboards = store.dashboards()
        self.assertEqual(len(dashboards), 1)
        self.assertEqual(dashboards[0].meta["format"], "platform")

    def test_upload_e_indexado(self):
        sync = KnowledgeSync(self.workspace)
        sync.add_upload("padrao.md", "# padrao interno\nusar timeseries para metricas")
        store = KnowledgeStore(self.workspace).build()
        self.assertTrue(store.search("padrao interno"))

    def test_html_para_texto(self):
        self.assertIn("titulo", html_to_text("<html><body><h1>titulo</h1><script>x</script>"))

    def test_glob_de_ingestao(self):
        self.assertTrue(_match("skills/dt-app-dashboards/SKILL.md", "skills/**"))
        self.assertFalse(_match("outro/arquivo.tf", "skills/**"))

    def test_sync_github_reporta_falha_sem_derrubar(self):
        def runner(cmd, timeout):
            raise RuntimeError("sem rede")

        sync = KnowledgeSync(self.workspace, runner=runner)
        result = sync.sync_github(only=["dynatrace-for-ai"])
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.ok, [])


class ServiceTest(TempWorkspaceTest):
    def service(self):
        return DashboardService(self.workspace, self.config)

    def test_fluxo_completo_offline_ate_aprovacao(self):
        service = self.service()
        profile = self.add_tenant()
        outcome = service.plan(
            "dashboard de SRE: taxa de erro e latencia dos servicos em producao",
            tenant=profile.name, probe=False,
        )
        proposal = outcome["proposal"]
        self.assertTrue(os.path.isfile(proposal.preview_path()))
        self.assertTrue(os.path.isfile(proposal.file("dashboard.json")))
        self.assertEqual(proposal.status(), "pendente")

        transport = FakeTransport({
            ("GET", "filter-segments:lean"): {"filterSegments": []},
            ("POST", "/filter-segments"): (201, {"uid": "seg-1"}),
            ("POST", "/platform/document/v1/documents"): (201, {"id": "doc-42"}),
        })
        service._clients[profile.name] = DynatraceClient(profile, transport=transport)

        result = service.approve(proposal.proposal_id, tenant=profile.name)
        self.assertEqual(result["result"].document_id, "doc-42")
        self.assertEqual(service.proposals.get(proposal.proposal_id).status(), "publicado")
        self.assertTrue(os.path.isfile(result["result"].template_path))
        # o template salvo deve aparecer na biblioteca para reuso
        self.assertTrue(service.library.entries(scope="clients"))

    def test_template_base_e_reaproveitado(self):
        service = self.service()
        first = service.plan("erros de log por servico", probe=False)
        path = service.save_as_template(first["proposal"].proposal_id, scope="library")
        self.assertTrue(os.path.isfile(path))
        ref = os.path.relpath(path, self.workspace.root)
        second = service.plan("kubernetes pods reiniciando", probe=False, base_template=ref)
        herdados = [t for t in second["spec"].tiles if "herdado do template base" in t.notes]
        self.assertTrue(herdados)

    def test_rejeicao_muda_o_status(self):
        service = self.service()
        outcome = service.plan("problemas ativos", probe=False)
        proposal = service.reject(outcome["proposal"].proposal_id, reason="faltou X")
        self.assertEqual(proposal.status(), "rejeitado")
        self.assertEqual(proposal.meta["reason"], "faltou X")


class CliTest(TempWorkspaceTest):
    def run_cli(self, *args):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(["--workspace", self.tmp] + list(args))
        return code, buffer.getvalue()

    def test_init_e_doctor(self):
        code, out = self.run_cli("init")
        self.assertEqual(code, 0)
        self.assertIn("workspace pronto", out)
        code, out = self.run_cli("doctor")
        self.assertEqual(code, 0)
        self.assertIn("workspace", out)

    def test_plan_preview_e_proposals(self):
        self.run_cli("init")
        code, out = self.run_cli(
            "plan", "monitorar erros de log e problemas ativos", "--offline", "--quiet"
        )
        self.assertEqual(code, 0)
        self.assertIn("proposta ...", out)
        proposal_id = [l for l in out.splitlines() if l.startswith("proposta")][0].split(":")[1].strip()
        code, out = self.run_cli("preview", proposal_id)
        self.assertEqual(code, 0)
        self.assertIn("DASHBOARD:", out)
        code, out = self.run_cli("proposals")
        self.assertIn(proposal_id, out)

    def test_catalog_lista_blueprints(self):
        code, out = self.run_cli("catalog", "--domain", "kubernetes")
        self.assertEqual(code, 0)
        self.assertIn("k8s.restarts", out)

    def test_tenants_add_e_list(self):
        self.run_cli("init")
        code, _ = self.run_cli("tenants", "add", "--name", "cli-tenant",
                               "--environment-id", "xyz98765", "--client", "Cliente")
        self.assertEqual(code, 0)
        code, out = self.run_cli("tenants", "list")
        self.assertIn("cli-tenant", out)
        self.assertIn("xyz98765.apps.dynatrace.com", out)

    def test_validate_detecta_erro(self):
        path = os.path.join(self.tmp, "ruim.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"name": "x", "content": {"tiles": {"1": {"type": "data", "query": "",
                                                                "visualization": "table"}},
                                                "layouts": {}}}, handle)
        code, out = self.run_cli("validate", path)
        self.assertEqual(code, 2)
        self.assertIn("erro", out)


class MultipartTest(unittest.TestCase):
    def test_parser_de_upload(self):
        body, content_type = encode_multipart(
            {"scope": "library"},
            [("files", "a.json", "application/json", b'{"x":1}'),
             ("files", "b.md", "text/markdown", b"# doc")],
        )
        parts = parse_multipart(body, content_type)
        self.assertEqual([p[0] for p in parts], ["a.json", "b.md"])
        self.assertEqual(parts[0][1], b'{"x":1}')


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
