"""Cliente das APIs da plataforma Dynatrace usadas pelo dtdash.

APIs cobertas
-------------
* Document API      -> ``/platform/document/v1/documents``            (dashboards)
* Environment share -> ``/platform/document/v1/environment-shares``
* Filter segments   -> ``/platform/storage/filter-segments/v1/filter-segments``
* Grail query API   -> ``/platform/storage/query/v1/query:{execute,poll,verify}``
"""

import json
import re
import time
import urllib.parse

from . import httpclient
from .auth import TokenProvider
from .errors import ApiError

DOCUMENTS_PATH = "/platform/document/v1/documents"
ENV_SHARES_PATH = "/platform/document/v1/environment-shares"
SEGMENTS_PATH = "/platform/storage/filter-segments/v1/filter-segments"
QUERY_PATH = "/platform/storage/query/v1"


ID_KEYS = ("id", "uid", "documentId", "document_id", "filterSegmentId", "segmentId")
VERSION_KEYS = ("version", "optimisticLockingVersion", "optimistic_locking_version")


def extract_id_pair(payload, extra_keys=()):
    """Devolve (chave, identificador) encontrados na resposta de criacao.

    As APIs de plataforma variam entre ``id``, ``uid`` e ``documentId`` conforme o
    servico e a versao; algumas embrulham o objeto em ``document``/``filterSegment``.
    Saber qual chave respondeu ajuda o ``dtdash selftest`` a reportar divergencias.
    """

    if not isinstance(payload, dict):
        return "", ""
    for key in tuple(extra_keys) + ID_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return key, value
    for wrapper in ("document", "filterSegment", "result", "data"):
        nested = payload.get(wrapper)
        if isinstance(nested, dict):
            key, value = extract_id_pair(nested, extra_keys)
            if value:
                return "%s.%s" % (wrapper, key), value
    return "", ""


def extract_id(payload, extra_keys=()):
    """Le o identificador de uma resposta de criacao."""

    return extract_id_pair(payload, extra_keys)[1]


def extract_version(payload):
    if not isinstance(payload, dict):
        return None
    for key in VERSION_KEYS:
        if payload.get(key) is not None:
            return payload[key]
    for wrapper in ("document", "filterSegment"):
        nested = payload.get(wrapper)
        if isinstance(nested, dict):
            found = extract_version(nested)
            if found is not None:
                return found
    return None


def _error_message(response):
    payload = response.json()
    if isinstance(payload, dict):
        error = payload.get("error") or payload
        if isinstance(error, dict):
            message = error.get("message") or error.get("detail") or ""
            details = error.get("details") or error.get("errorDetails")
            if details:
                message = "%s | %s" % (message, json.dumps(details, ensure_ascii=False)[:400])
            if message:
                return message
    return (response.text or "")[:500] or "erro desconhecido"


class DynatraceClient(object):
    def __init__(self, profile, transport=None, token_provider=None, sleep=time.sleep):
        self.profile = profile
        self._transport = transport or httpclient.request
        self.tokens = token_provider or TokenProvider(profile, transport=self._transport)
        self._sleep = sleep
        self.call_log = []

    # ------------------------------------------------------------- transporte
    def _url(self, path, params=None):
        url = self.profile.platform_url.rstrip("/") + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)
        return url

    def call(self, method, path, params=None, json_body=None, multipart=None, headers=None,
             timeout=httpclient.DEFAULT_TIMEOUT, raw_url=None):
        url = raw_url or self._url(path, params)
        head = {"Authorization": self.tokens.authorization()}
        head.update(headers or {})
        data = None
        if json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            head.setdefault("Content-Type", "application/json")
        elif multipart is not None:
            fields, files = multipart
            data, content_type = httpclient.encode_multipart(fields, files)
            head["Content-Type"] = content_type
        response = self._transport(
            method, url, headers=head, data=data, timeout=timeout,
            verify=self.profile.verify_tls,
        )
        self.call_log.append(
            {"method": method.upper(), "url": url, "status": response.status}
        )
        return response

    def _expect(self, response, action):
        if not response.ok:
            raise ApiError(
                "%s falhou: %s" % (action, _error_message(response)),
                status=response.status,
                url=response.url,
                payload=response.json(),
            )
        return response

    # -------------------------------------------------------------- documentos
    def list_documents(self, doc_type="dashboard", page_size=100, name_filter=None):
        parts = []
        if doc_type:
            parts.append("type == '%s'" % doc_type)
        if name_filter:
            parts.append("name contains '%s'" % name_filter.replace("'", ""))
        response = self.call(
            "GET",
            DOCUMENTS_PATH,
            params={"filter": " and ".join(parts) or None, "page-size": page_size},
        )
        self._expect(response, "listagem de documentos")
        payload = response.json() or {}
        if isinstance(payload, list):
            return payload
        for key in ("documents", "results", "items", "content"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def get_document(self, document_id):
        response = self.call("GET", "%s/%s" % (DOCUMENTS_PATH, document_id))
        self._expect(response, "leitura de documento")
        return response.json() or {}

    def get_document_content(self, document_id):
        response = self.call("GET", "%s/%s/content" % (DOCUMENTS_PATH, document_id))
        if response.ok:
            payload = response.json()
            if payload is not None:
                return payload
        # fallback: a resposta de /documents/{id} vem como multipart
        response = self.call("GET", "%s/%s" % (DOCUMENTS_PATH, document_id))
        self._expect(response, "leitura do conteudo do documento")
        payload = response.json()
        if isinstance(payload, dict) and "content" in payload:
            content = payload["content"]
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except ValueError:
                    return {"raw": content}
            return content
        return _parse_multipart_json(response)

    def create_document(self, name, content, doc_type="dashboard", description=None,
                        is_private=False):
        body = json.dumps(content, ensure_ascii=False, indent=2)
        fields = {"name": name, "type": doc_type, "isPrivate": "true" if is_private else "false"}
        if description:
            fields["description"] = description
        files = [("content", "%s.json" % _slug(name), "application/json", body)]
        response = self.call("POST", DOCUMENTS_PATH, multipart=(fields, files))
        self._expect(response, "criacao do dashboard")
        payload = response.json() or {}
        key, value = extract_id_pair(payload)
        if value:
            payload.setdefault("_idKey", key)
            payload["id"] = value
        return payload

    def update_document(self, document_id, content, name=None, version=None,
                        doc_type="dashboard"):
        body = json.dumps(content, ensure_ascii=False, indent=2)
        fields = {"type": doc_type}
        if name:
            fields["name"] = name
        files = [("content", "dashboard.json", "application/json", body)]
        response = self.call(
            "PATCH",
            "%s/%s" % (DOCUMENTS_PATH, document_id),
            params={"optimistic-locking-version": version} if version else None,
            multipart=(fields, files),
        )
        self._expect(response, "atualizacao do dashboard")
        return response.json() or {}

    def delete_document(self, document_id, version=None):
        response = self.call(
            "DELETE",
            "%s/%s" % (DOCUMENTS_PATH, document_id),
            params={"optimistic-locking-version": version} if version else None,
        )
        self._expect(response, "remocao do documento")
        return True

    def share_document_with_environment(self, document_id, access="read"):
        """Disponibiliza o dashboard para todo o ambiente (view-only).

        Caminho principal: environment-shares. Se o tenant nao expuser esse
        recurso, cai para ``PATCH /documents/{id}`` com ``isPrivate=false``.
        """

        response = self.call(
            "POST",
            ENV_SHARES_PATH,
            json_body={"documentId": document_id, "access": access},
        )
        if response.status == 409:  # ja compartilhado
            return {"documentId": document_id, "status": "already-shared"}
        if response.status in (404, 405, 501):
            return self._share_via_patch(document_id)
        self._expect(response, "compartilhamento do dashboard")
        payload = response.json() or {}
        payload.setdefault("method", "environment-shares")
        return payload

    def _share_via_patch(self, document_id):
        metadata = {}
        try:
            metadata = self.get_document(document_id)
        except ApiError:
            pass
        version = extract_version(metadata)
        response = self.call(
            "PATCH",
            "%s/%s" % (DOCUMENTS_PATH, document_id),
            params={"optimistic-locking-version": version} if version else None,
            multipart=({"isPrivate": "false"}, []),
        )
        self._expect(response, "compartilhamento do dashboard (isPrivate)")
        payload = response.json() or {}
        payload.setdefault("method", "patch-isPrivate")
        return payload

    # ----------------------------------------------------------------- segments
    def list_segments(self, lean=True):
        path = SEGMENTS_PATH + (":lean" if lean else "")
        response = self.call("GET", path, params={"add-fields": "INCLUDES"} if not lean else None)
        if not response.ok and lean:
            response = self.call("GET", SEGMENTS_PATH)
        self._expect(response, "listagem de segments")
        payload = response.json() or {}
        if isinstance(payload, list):
            return payload
        for key in ("filterSegments", "segments", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def create_segment(self, segment):
        response = self.call("POST", SEGMENTS_PATH, json_body=segment)
        self._expect(response, "criacao do segment '%s'" % segment.get("name"))
        payload = response.json() or {}
        key, value = extract_id_pair(payload)
        if value:
            payload.setdefault("_idKey", key)
            payload["uid"] = value
        return payload

    def delete_segment(self, uid, version=None):
        response = self.call(
            "DELETE",
            "%s/%s" % (SEGMENTS_PATH, uid),
            params={"optimistic-locking-version": version} if version else None,
        )
        if response.status == 404:
            return False
        self._expect(response, "remocao do segment")
        return True

    def get_segment(self, uid):
        response = self.call("GET", "%s/%s" % (SEGMENTS_PATH, uid))
        self._expect(response, "leitura do segment")
        return response.json() or {}

    def find_segment_by_name(self, name):
        for segment in self.list_segments():
            if (segment.get("name") or "").strip().lower() == (name or "").strip().lower():
                return segment
        return None

    # -------------------------------------------------------------------- DQL
    def verify_query(self, dql):
        """Valida a sintaxe de uma DQL sem executa-la."""

        response = self.call(
            "POST", "%s/query:verify" % QUERY_PATH, json_body={"query": dql}
        )
        if response.status in (404, 405):
            return None  # endpoint indisponivel neste tenant
        payload = response.json() or {}
        if not response.ok:
            return {
                "valid": False,
                "notifications": [{"severity": "ERROR", "message": _error_message(response)}],
            }
        notifications = payload.get("notifications") or []
        valid = payload.get("valid")
        if valid is None:
            valid = not any(
                (n.get("severity") or "").upper() == "ERROR" for n in notifications
            )
        return {"valid": bool(valid), "notifications": notifications}

    def execute_query(self, dql, max_records=100, timeframe=None, timeout_ms=30000,
                      poll_timeout=60.0):
        body = {
            "query": dql,
            "maxResultRecords": max_records,
            "requestTimeoutMilliseconds": timeout_ms,
            "fetchTimeoutSeconds": 60,
        }
        if timeframe:
            body["defaultTimeframeStart"] = timeframe[0]
            body["defaultTimeframeEnd"] = timeframe[1]
        response = self.call("POST", "%s/query:execute" % QUERY_PATH, json_body=body)
        self._expect(response, "execucao de DQL")
        payload = response.json() or {}
        deadline = time.time() + poll_timeout
        while (payload.get("state") or "").upper() in ("RUNNING", "NOT_STARTED", ""):
            token = payload.get("requestToken")
            if not token:
                break
            if time.time() > deadline:
                raise ApiError("timeout aguardando resultado da DQL")
            self._sleep(1.0)
            poll = self.call(
                "GET", "%s/query:poll" % QUERY_PATH, params={"request-token": token}
            )
            self._expect(poll, "poll de DQL")
            payload = poll.json() or {}
        result = payload.get("result") or {}
        return {
            "state": payload.get("state"),
            "records": result.get("records") or [],
            "metadata": result.get("metadata") or {},
            "notifications": payload.get("notifications") or [],
        }

    # ------------------------------------------------------------- descoberta
    def data_objects(self):
        try:
            result = self.execute_query(
                "fetch dt.system.data_objects | fields name, type | sort name asc",
                max_records=500,
            )
        except ApiError:
            return []
        return [r.get("name") for r in result["records"] if r.get("name")]

    def describe(self, data_object, limit=400):
        result = self.execute_query("describe %s" % data_object, max_records=limit)
        fields = []
        for record in result["records"]:
            name = record.get("field") or record.get("name") or record.get("column")
            if name:
                fields.append(name)
        return fields


def _parse_multipart_json(response):
    """Extrai o primeiro objeto JSON de uma resposta multipart."""

    text = response.text or ""
    match = re.search(r"(\{.*\})", text, re.S)
    if not match:
        raise ApiError("resposta multipart sem conteudo JSON", url=response.url)
    try:
        return json.loads(match.group(1))
    except ValueError as exc:
        raise ApiError("conteudo multipart invalido: %s" % exc, url=response.url)


def _slug(value):
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "dashboard")).strip("-")
    return (slug or "dashboard")[:80]
