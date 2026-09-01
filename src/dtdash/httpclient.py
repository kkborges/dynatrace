"""Cliente HTTP minimalista (somente biblioteca padrao).

Respeita as variaveis de ambiente de proxy (HTTPS_PROXY/NO_PROXY) atraves do
urllib e aceita um CA bundle customizado via DTDASH_CA_BUNDLE.
"""

import json
import os
import ssl
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

from .errors import ApiError

DEFAULT_TIMEOUT = float(os.environ.get("DTDASH_HTTP_TIMEOUT", "60"))
DEFAULT_RETRIES = int(os.environ.get("DTDASH_HTTP_RETRIES", "3"))
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
USER_AGENT = "dtdash/1.0 (+dynatrace-dashboard-builder)"


class Response(object):
    def __init__(self, status, headers, body, url):
        self.status = status
        self.headers = headers or {}
        self.body = body or b""
        self.url = url

    @property
    def text(self):
        try:
            return self.body.decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover
            return self.body.decode("latin-1", "replace")

    def json(self):
        if not self.body:
            return None
        try:
            return json.loads(self.text)
        except ValueError:
            return None

    @property
    def ok(self):
        return 200 <= self.status < 300


def _ssl_context(verify=True):
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ca_bundle = os.environ.get("DTDASH_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if ca_bundle and os.path.isfile(ca_bundle):
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def request(
    method,
    url,
    headers=None,
    data=None,
    timeout=DEFAULT_TIMEOUT,
    retries=DEFAULT_RETRIES,
    verify=True,
    backoff=1.0,
    sleep=time.sleep,
):
    """Executa uma requisicao HTTP com retry exponencial."""

    headers = dict(headers or {})
    headers.setdefault("User-Agent", USER_AGENT)
    headers.setdefault("Accept", "application/json")
    context = _ssl_context(verify)
    last_error = None

    for attempt in range(max(1, retries) + 1):
        req = urllib.request.Request(url, data=data, method=method.upper())
        for key, value in headers.items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
                return Response(
                    resp.getcode(), dict(resp.headers.items()), resp.read(), url
                )
        except urllib.error.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
            except Exception:  # pragma: no cover - stream ja consumido
                pass
            response = Response(exc.code, dict(exc.headers.items() if exc.headers else {}), body, url)
            if exc.code in RETRY_STATUS and attempt < retries:
                last_error = response
                sleep(backoff * (2 ** attempt))
                continue
            return response
        except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
            last_error = exc
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
                continue
            raise ApiError("falha de rede ao chamar %s: %s" % (url, exc), url=url)

    if isinstance(last_error, Response):  # pragma: no cover - defensivo
        return last_error
    raise ApiError("falha ao chamar %s" % url, url=url)


def encode_form(fields):
    """Codifica um dicionario como application/x-www-form-urlencoded."""

    return urllib.parse.urlencode(fields).encode("utf-8")


def encode_multipart(fields, files):
    """Codifica multipart/form-data.

    fields: dict de campos simples (str)
    files: lista de tuplas (nome, filename, content_type, bytes)
    """

    boundary = "----dtdash%s" % uuid.uuid4().hex
    out = []
    for name, value in (fields or {}).items():
        if value is None:
            continue
        out.append(("--%s\r\n" % boundary).encode("utf-8"))
        out.append(
            ('Content-Disposition: form-data; name="%s"\r\n\r\n' % name).encode("utf-8")
        )
        out.append(("%s\r\n" % value).encode("utf-8"))
    for name, filename, content_type, payload in files or []:
        out.append(("--%s\r\n" % boundary).encode("utf-8"))
        out.append(
            (
                'Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
                % (name, filename)
            ).encode("utf-8")
        )
        out.append(("Content-Type: %s\r\n\r\n" % content_type).encode("utf-8"))
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        out.append(payload)
        out.append(b"\r\n")
    out.append(("--%s--\r\n" % boundary).encode("utf-8"))
    body = b"".join(out)
    return body, "multipart/form-data; boundary=%s" % boundary
