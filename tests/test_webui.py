import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from tests.helpers import TempWorkspaceTest, _response
from tests.test_metrics_permissions import FakeGrail, GRAIL_KEYS

from dtdash.client import DynatraceClient
from dtdash.errors import ConfigError
from dtdash.server import DtDashHandler
from dtdash.service import DashboardService
from dtdash.webauth import SessionStore, UserStore


class UserStoreTest(TempWorkspaceTest):
    def store(self):
        return UserStore(self.workspace)

    def test_cria_e_autentica(self):
        store = self.store()
        self.assertTrue(store.empty())
        store.add("ana", "senha-super-segura", role="operador")
        self.assertFalse(store.empty())
        self.assertIsNotNone(store.authenticate("ana", "senha-super-segura"))
        self.assertIsNone(store.authenticate("ana", "errada"))
        self.assertIsNone(store.authenticate("desconhecida", "x"))

    def test_senha_nao_e_gravada_em_claro(self):
        store = self.store()
        store.add("ana", "senha-super-segura")
        with open(store.path, encoding="utf-8") as handle:
            conteudo = handle.read()
        self.assertNotIn("senha-super-segura", conteudo)
        self.assertIn("salt", conteudo)

    def test_arquivo_so_para_o_dono(self):
        store = self.store()
        store.add("ana", "senha-super-segura")
        modo = os.stat(store.path).st_mode & 0o777
        self.assertEqual(modo, 0o600)

    def test_regras_de_cadastro(self):
        store = self.store()
        self.assertRaises(ConfigError, store.add, "ana", "curta")
        self.assertRaises(ConfigError, store.add, "ana", "senha-super-segura", "papel-invalido")
        store.add("ana", "senha-super-segura")
        self.assertRaises(ConfigError, store.remove, "ana")  # ultimo usuario
        store.add("bob", "outra-senha-segura")
        store.remove("ana")
        self.assertEqual(store.names(), ["bob"])

    def test_troca_de_senha(self):
        store = self.store()
        store.add("ana", "senha-super-segura")
        store.set_password("ana", "nova-senha-segura")
        self.assertIsNone(store.authenticate("ana", "senha-super-segura"))
        self.assertIsNotNone(store.authenticate("ana", "nova-senha-segura"))

    def test_bootstrap_gera_senha_aleatoria(self):
        store = self.store()
        name, password = store.bootstrap_admin()
        self.assertEqual(name, "admin")
        self.assertGreaterEqual(len(password), 12)
        self.assertIsNotNone(store.authenticate("admin", password))


class SessionStoreTest(unittest.TestCase):
    def test_ciclo_de_sessao(self):
        agora = [1000.0]
        store = SessionStore(ttl=60, clock=lambda: agora[0])
        token = store.create({"name": "ana", "role": "admin", "fullName": "Ana"})
        self.assertEqual(store.get(token)["user"], "ana")
        agora[0] += 30
        self.assertIsNotNone(store.get(token))     # sessao deslizante
        agora[0] += 61
        self.assertIsNone(store.get(token))

    def test_logout_invalida(self):
        store = SessionStore()
        token = store.create({"name": "ana", "role": "admin"})
        store.destroy(token)
        self.assertIsNone(store.get(token))


class WebServerTest(TempWorkspaceTest):
    """Sobe o servidor de verdade e exercita o fluxo pela HTTP."""

    def setUp(self):
        super().setUp()
        self.service = DashboardService(self.workspace, self.config)
        self.users = UserStore(self.workspace)
        self.users.add("ana", "senha-super-segura", role="admin", full_name="Ana")
        self.users.add("leitor", "senha-super-segura", role="leitor")
        DtDashHandler.service = self.service
        DtDashHandler.users = self.users
        DtDashHandler.sessions = SessionStore()
        DtDashHandler.token = ""
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), DtDashHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = ""
        time.sleep(0.05)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    # ---------------------------------------------------------------- infra
    def request(self, path, method="GET", body=None, csrf=True, cookie=None, raw=False):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-Requested-With"] = "dtdash"
        jar = cookie if cookie is not None else self.cookie
        if jar:
            headers["Cookie"] = jar
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                return (response.status, dict(response.headers.items()),
                        payload if raw else _maybe_json(payload))
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers.items()), _maybe_json(exc.read())

    def login(self, user="ana", password="senha-super-segura"):
        status, headers, payload = self.request(
            "/api/login", "POST", {"user": user, "password": password})
        if status == 200:
            self.cookie = headers["Set-Cookie"].split(";")[0]
        return status, payload

    # ------------------------------------------------------------ requisitos
    def test_pagina_inicial_redireciona_sem_sessao(self):
        status, headers, _ = self.request("/")
        self.assertIn(status, (302, 200))
        if status == 302:
            self.assertEqual(headers["Location"], "/login")

    def test_login_valido_e_invalido(self):
        status, payload = self.login("ana", "errada")
        self.assertEqual(status, 401)
        status, payload = self.login()
        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["role"], "admin")
        self.assertIn("HttpOnly", self.cookieheaders())

    def cookieheaders(self):
        status, headers, _ = self.request(
            "/api/login", "POST", {"user": "ana", "password": "senha-super-segura"})
        return headers.get("Set-Cookie", "")

    def test_api_exige_sessao(self):
        status, _, payload = self.request("/api/state")
        self.assertEqual(status, 401)
        self.login()
        status, _, payload = self.request("/api/state")
        self.assertEqual(status, 200)
        self.assertIn("tenants", payload)

    def test_escrita_exige_cabecalho_anti_csrf(self):
        self.login()
        status, _, payload = self.request("/api/tenants", "POST", {"name": "x"}, csrf=False)
        self.assertEqual(status, 400)
        self.assertIn("CSRF", payload["error"])

    def test_leitor_nao_publica_nem_cadastra(self):
        self.login("leitor", "senha-super-segura")
        status, _, payload = self.request(
            "/api/tenants", "POST", {"name": "acme", "environmentId": "abc12345"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("/api/state")
        self.assertEqual(status, 200, "leitor continua podendo consultar")

    def test_logout_encerra_a_sessao(self):
        self.login()
        self.request("/api/logout", "POST", {})
        status, _, _ = self.request("/api/state")
        self.assertEqual(status, 401)

    def test_cadastro_de_cliente_e_listagem(self):
        self.login()
        status, _, payload = self.request("/api/tenants", "POST", {
            "name": "acme", "client": "Acme S.A.", "environmentId": "abc12345",
            "tokenEnv": "DT_TOKEN_ACME", "notes": "cliente piloto",
        })
        self.assertEqual(status, 200, payload)
        status, _, tenants = self.request("/api/tenants")
        self.assertEqual(len(tenants), 1)
        self.assertEqual(tenants[0]["client"], "Acme S.A.")
        self.assertEqual(tenants[0]["platformUrl"], "https://abc12345.apps.dynatrace.com")
        self.assertFalse(tenants[0]["hasCredentials"])

    def test_edicao_e_exclusao_de_cliente(self):
        self.login()
        self.request("/api/tenants", "POST", {"name": "acme", "environmentId": "abc12345"})
        self.request("/api/tenants", "POST", {"name": "acme", "client": "Novo Nome"})
        status, _, tenants = self.request("/api/tenants")
        self.assertEqual(tenants[0]["client"], "Novo Nome")
        status, _, _ = self.request("/api/tenants/acme/delete", "POST", {})
        self.assertEqual(status, 200)
        status, _, tenants = self.request("/api/tenants")
        self.assertEqual(tenants, [])

    def test_fluxo_completo_prompt_previa_aprovacao_historico(self):
        self.login()
        profile = self.add_tenant(name="acme")
        self.service._clients["acme"] = DynatraceClient(
            profile, transport=FakeGrail(metric_index=GRAIL_KEYS))

        status, _, plano = self.request("/api/plan", "POST", {
            "description": "saude dos hosts e servicos em producao com taxa de erro",
            "tenant": "acme", "offline": True,
        })
        self.assertEqual(status, 200, plano)
        self.assertGreater(plano["tiles"], 3)

        status, _, preview = self.request(plano["previewUrl"], raw=True)
        self.assertEqual(status, 200)
        self.assertIn(b"Necessidades atendidas", preview)

        self.service._clients["acme"] = DynatraceClient(profile, transport=_FakeDeploy())
        status, _, resultado = self.request(
            "/api/proposals/%s/approve" % plano["proposalId"], "POST",
            {"tenant": "acme", "client": "Acme S.A."})
        self.assertEqual(status, 200, resultado)
        self.assertEqual(resultado["documentId"], "doc-1")

        status, _, historico = self.request("/api/history")
        self.assertEqual(len(historico), 1)
        self.assertEqual(historico[0]["documentId"], "doc-1")
        self.assertEqual(historico[0]["user"], "ana")
        self.assertEqual(historico[0]["client"], "Acme S.A.")

        status, _, clientes = self.request("/api/clients")
        self.assertEqual(clientes[0]["client"], "Acme S.A.")
        self.assertEqual(clientes[0]["dashboards"], 1)

        status, _, state = self.request("/api/state")
        self.assertEqual(state["deployments"], 1)

    def test_historico_filtra_por_cliente(self):
        self.login()
        status, _, historico = self.request("/api/history?client=inexistente")
        self.assertEqual(historico, [])

    def test_arquivos_estaticos_e_login_sao_publicos(self):
        for path in ("/login", "/static/style.css", "/static/app.js"):
            status, _, _ = self.request(path, raw=True)
            self.assertEqual(status, 200, path)

    def test_static_nao_permite_travessia_de_caminho(self):
        self.login()
        for path in ("/static/../config.py", "/static/..%2Fconfig.py",
                     "/static/../../../etc/passwd"):
            status, _, body = self.request(path, raw=True)
            self.assertNotEqual(status, 200, path)
            texto = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.assertNotIn(b"import ", texto, path)
            self.assertNotIn(b"root:", texto, path)


class _FakeDeploy(object):
    def __call__(self, method, url, headers=None, data=None, **kwargs):
        if "filter-segments" in url and method.upper() == "GET":
            return _response(200, {"filterSegments": []}, url)
        if "filter-segments" in url:
            return _response(201, {"uid": "seg-1"}, url)
        if "/documents" in url and method.upper() == "POST":
            return _response(201, {"id": "doc-1"}, url)
        return _response(200, {}, url)


def _maybe_json(payload):
    try:
        return json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return payload


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
