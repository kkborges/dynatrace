"""Utilitarios comuns aos testes."""

import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dtdash.config import Config, TenantProfile, Workspace  # noqa: E402
from dtdash.httpclient import Response  # noqa: E402


class TempWorkspaceTest(unittest.TestCase):
    """Cria um workspace isolado com a base de conhecimento semente."""

    seed_knowledge = True

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dtdash-test-")
        self.workspace = Workspace(self.tmp)
        self.workspace.ensure()
        if self.seed_knowledge:
            source = os.path.join(ROOT, "knowledge", "seed")
            if os.path.isdir(source):
                shutil.copytree(source, self.workspace.knowledge_seed_dir, dirs_exist_ok=True)
        self.config = Config(self.workspace, {"tenants": {}, "settings": {}})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add_tenant(self, name="teste", token="dt0s16.FAKE"):
        os.environ["DT_PLATFORM_TOKEN_TESTE"] = token
        profile = TenantProfile(
            name=name, environment_id="abc12345", client_name="Cliente Teste",
            platform_token_env="DT_PLATFORM_TOKEN_TESTE",
        )
        self.config.put_tenant(profile)
        return profile


class FakeTransport(object):
    """Transporte HTTP falso: mapeia (metodo, sufixo da url) -> resposta."""

    def __init__(self, routes=None, default=None):
        self.routes = routes or {}
        self.default = default or (200, {})
        self.calls = []

    def __call__(self, method, url, headers=None, data=None, timeout=None, verify=True, **kw):
        self.calls.append({"method": method, "url": url, "data": data, "headers": headers})
        for (route_method, fragment), payload in self.routes.items():
            if route_method == method.upper() and fragment in url:
                status, body = payload if isinstance(payload, tuple) else (200, payload)
                return _response(status, body, url)
        status, body = self.default
        return _response(status, body, url)


def _response(status, body, url):
    if isinstance(body, (dict, list)):
        raw = json.dumps(body).encode("utf-8")
    elif isinstance(body, str):
        raw = body.encode("utf-8")
    else:
        raw = body or b""
    return Response(status, {"Content-Type": "application/json"}, raw, url)
