import json
import unittest

from tests.helpers import FakeTransport, TempWorkspaceTest

from dtdash.auth import TokenProvider
from dtdash.client import DynatraceClient
from dtdash.capabilities import TenantCapabilities
from dtdash.config import TenantProfile
from dtdash.deploy import Deployer
from dtdash.errors import ApiError, AuthError, ValidationError
from dtdash.spec import DashboardSpec, SegmentSpec, TileSpec


def profile(auth="platform_token"):
    return TenantProfile(
        name="t", environment_id="abc12345", auth_method=auth,
        platform_token="dt0s16.TOKEN", oauth_client_id="cid", oauth_client_secret="secret",
    ).normalize()


class AuthTest(unittest.TestCase):
    def test_platform_token_vai_direto_no_header(self):
        provider = TokenProvider(profile())
        self.assertEqual(provider.authorization(), "Bearer dt0s16.TOKEN")

    def test_oauth_troca_credenciais_por_token(self):
        transport = FakeTransport({("POST", "sso.dynatrace.com"): {
            "access_token": "abc", "expires_in": 300}})
        provider = TokenProvider(profile("oauth"), transport=transport)
        self.assertEqual(provider.access_token(), "abc")
        provider.access_token()
        self.assertEqual(len(transport.calls), 1, "o token deve ser cacheado")

    def test_oauth_falho_gera_erro(self):
        transport = FakeTransport({("POST", "sso.dynatrace.com"): (401, {"error": "nope"})})
        provider = TokenProvider(profile("oauth"), transport=transport)
        self.assertRaises(AuthError, provider.access_token)


class ClientTest(unittest.TestCase):
    def client(self, routes, default=None):
        transport = FakeTransport(routes, default)
        return DynatraceClient(profile(), transport=transport), transport

    def test_cria_dashboard_com_multipart(self):
        client, transport = self.client({("POST", "/platform/document/v1/documents"): (
            201, {"id": "doc-1", "name": "T"})})
        created = client.create_document("Meu Dash", {"version": 21, "tiles": {}})
        self.assertEqual(created["id"], "doc-1")
        call = transport.calls[-1]
        body = call["data"].decode("utf-8")
        self.assertIn('name="name"', body)
        self.assertIn("Meu Dash", body)
        self.assertIn('name="type"', body)
        self.assertIn("dashboard", body)
        self.assertIn('filename="Meu-Dash.json"', body)
        self.assertIn("multipart/form-data; boundary=", call["headers"]["Content-Type"])

    def test_erro_de_api_vira_excecao(self):
        client, _ = self.client({("POST", "/documents"): (403, {"error": {
            "message": "sem permissao"}})})
        with self.assertRaises(ApiError) as ctx:
            client.create_document("x", {})
        self.assertIn("sem permissao", str(ctx.exception))

    def test_lista_segments(self):
        client, _ = self.client({("GET", "filter-segments:lean"): {
            "filterSegments": [{"uid": "u1", "name": "Producao"}]}})
        self.assertEqual(client.find_segment_by_name("producao")["uid"], "u1")

    def test_cria_segment(self):
        client, transport = self.client({("POST", "/filter-segments"): (
            201, {"uid": "seg-1", "name": "N"})})
        created = client.create_segment({"name": "N", "isPublic": True, "includes": []})
        self.assertEqual(created["uid"], "seg-1")
        self.assertEqual(json.loads(transport.calls[-1]["data"])["name"], "N")

    def test_execucao_de_dql_faz_poll(self):
        routes = {
            ("POST", "query:execute"): {"state": "RUNNING", "requestToken": "tok"},
            ("GET", "query:poll"): {"state": "SUCCEEDED",
                                    "result": {"records": [{"a": 1}], "metadata": {}}},
        }
        client, _ = self.client(routes)
        client._sleep = lambda _s: None
        outcome = client.execute_query("fetch logs")
        self.assertEqual(outcome["state"], "SUCCEEDED")
        self.assertEqual(len(outcome["records"]), 1)

    def test_verify_indisponivel_retorna_none(self):
        client, _ = self.client({("POST", "query:verify"): (404, {})})
        self.assertIsNone(client.verify_query("fetch logs"))

    def test_verify_invalido(self):
        client, _ = self.client({("POST", "query:verify"): {
            "valid": False, "notifications": [{"severity": "ERROR", "message": "erro de sintaxe"}]}})
        result = client.verify_query("fetch")
        self.assertFalse(result["valid"])

    def test_url_do_dashboard(self):
        self.assertEqual(
            profile().dashboard_url("doc-9"),
            "https://abc12345.apps.dynatrace.com/ui/apps/dynatrace.dashboards/dashboard/doc-9",
        )


class CapabilitiesTest(unittest.TestCase):
    def test_probe_detecta_dps(self):
        routes = {
            ("POST", "query:execute"): {"state": "SUCCEEDED", "result": {"records": [
                {"name": "logs"}, {"name": "dt.system.events"}]}},
        }
        transport = FakeTransport(routes)
        client = DynatraceClient(profile(), transport=transport)
        caps = TenantCapabilities.probe(client)
        self.assertTrue(caps.online)
        self.assertTrue(caps.grail_queryable)
        self.assertIn("logs", caps.data_objects)
        self.assertTrue(caps.dps)

    def test_probe_sem_eventos_de_billing(self):
        calls = {"n": 0}

        def transport(method, url, **kwargs):
            calls["n"] += 1
            records = [{"name": "logs"}] if calls["n"] == 1 else []
            from tests.helpers import _response
            return _response(200, {"state": "SUCCEEDED", "result": {"records": records}}, url)

        client = DynatraceClient(profile(), transport=transport)
        caps = TenantCapabilities.probe(client)
        self.assertIs(caps.dps, False)
        self.assertIn("nao detectado", caps.license_label())


class DeployTest(TempWorkspaceTest):
    def spec(self):
        return DashboardSpec(
            name="Dash de Teste",
            description="d",
            client_name="acme",
            segments=[SegmentSpec(key="namespace-pag", name="Namespace pag", dimension="namespace",
                                  value="pag",
                                  includes=[{"dataObject": "logs",
                                             "filter": 'k8s.namespace.name == "pag"'}])],
            tiles=[TileSpec(tile_id="1", title="Erros", query="fetch logs",
                            visualization="table", segments=["namespace-pag"])],
        )

    def deployer(self, routes):
        transport = FakeTransport(routes)
        client = DynatraceClient(profile(), transport=transport)
        return Deployer(client, self.workspace), transport

    def test_deploy_cria_segment_dashboard_e_template(self):
        routes = {
            ("GET", "filter-segments:lean"): {"filterSegments": []},
            ("POST", "/filter-segments"): (201, {"uid": "seg-1"}),
            ("POST", "/platform/document/v1/documents"): (201, {"id": "doc-7"}),
        }
        deployer, transport = self.deployer(routes)
        spec = self.spec()
        result, document, report = deployer.deploy(spec)
        self.assertEqual(result.document_id, "doc-7")
        self.assertIn("doc-7", result.url)
        self.assertEqual(document["content"]["tiles"]["1"]["segments"], ["seg-1"])
        self.assertTrue(result.template_path.endswith(".json"))
        self.assertIn("clients", result.template_path)
        self.assertTrue(report.ok)

    def test_deploy_reaproveita_segment_existente(self):
        routes = {
            ("GET", "filter-segments:lean"): {"filterSegments": [
                {"uid": "existente", "name": "Namespace pag"}]},
            ("POST", "/platform/document/v1/documents"): (201, {"id": "doc-8"}),
        }
        deployer, transport = self.deployer(routes)
        result, document, _ = deployer.deploy(self.spec())
        self.assertEqual(document["content"]["tiles"]["1"]["segments"], ["existente"])
        self.assertFalse(any(c["url"].endswith("/filter-segments") and c["method"] == "POST"
                             for c in transport.calls))

    def test_dry_run_nao_chama_a_api(self):
        deployer, transport = self.deployer({})
        result, _document, _report = deployer.deploy(self.spec(), dry_run=True)
        self.assertEqual(result.document_id, "(dry-run)")
        self.assertEqual(transport.calls, [])

    def test_deploy_bloqueia_dashboard_invalido(self):
        deployer, _ = self.deployer({})
        spec = self.spec()
        spec.tiles[0].query = ""
        self.assertRaises(ValidationError, deployer.deploy, spec)

    def test_compartilhamento_com_o_ambiente(self):
        routes = {
            ("GET", "filter-segments:lean"): {"filterSegments": []},
            ("POST", "/filter-segments"): (201, {"uid": "seg-1"}),
            ("POST", "/platform/document/v1/documents"): (201, {"id": "doc-9"}),
            ("POST", "/environment-shares"): (201, {"id": "share-1"}),
        }
        deployer, _ = self.deployer(routes)
        result, _document, _report = deployer.deploy(self.spec(), share=True)
        self.assertTrue(result.shared)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
