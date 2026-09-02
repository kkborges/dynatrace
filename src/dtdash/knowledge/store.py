"""Indice e busca da base de conhecimento (BM25 simplificado, stdlib apenas)."""

import json
import math
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".dql", ".jsonc", ".yaml", ".yml"}
JSON_EXTENSIONS = {".json"}
MAX_FILE_BYTES = 400_000
SNIPPET_CHARS = 320

STOPWORDS = set(
    """
    a as o os um uma uns umas de do da dos das em no na nos nas por para com sem sob
    sobre entre ate e ou que qual quais quando onde como se ao aos à às pelo pela
    isso este esta esse essa aquele aquela seu sua seus suas meu minha nosso nossa
    ser estar tem ter todos todas mais menos muito muita quero preciso gostaria
    the of and or to in on for with a an is are be was were this that these those
    i we you they it my our your their from by as at into about please need want
    dashboard dashboards painel paineis
    """.split()
)


def strip_accents(value):
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn"
    )


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.\-]*")


def tokenize(text, keep_stopwords=False):
    text = strip_accents((text or "").lower())
    tokens = []
    for raw in TOKEN_RE.findall(text):
        token = raw.strip("._-")
        if len(token) < 2:
            continue
        if not keep_stopwords and token in STOPWORDS:
            continue
        tokens.append(token)
        # tokens compostos (ex.: dt.host.cpu.usage) tambem geram partes
        if "." in token or "-" in token or "_" in token:
            for part in re.split(r"[._-]+", token):
                if len(part) >= 3 and (keep_stopwords or part not in STOPWORDS):
                    tokens.append(part)
    return tokens


@dataclass
class KnowledgeDoc:
    doc_id: str
    title: str
    source: str            # seed | github | docs | example | upload | library | client
    kind: str              # reference | dashboard | dql | requirement | other
    path: str
    text: str = ""
    tags: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_meta(self):
        return {
            "id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "kind": self.kind,
            "path": self.path,
            "tags": self.tags,
            "meta": self.meta,
        }


@dataclass
class SearchHit:
    doc: KnowledgeDoc
    score: float
    snippet: str = ""

    def to_dict(self):
        return {
            "title": self.doc.title,
            "source": self.doc.source,
            "kind": self.doc.kind,
            "path": self.doc.path,
            "score": round(self.score, 3),
            "snippet": self.snippet,
        }


class KnowledgeStore(object):
    """Indexa arquivos locais e responde buscas por relevancia."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.docs = {}
        self._df = {}
        self._postings = {}
        self._lengths = {}
        self._avg_len = 1.0
        self.built_at = 0.0

    # ------------------------------------------------------------------ roots
    def roots(self):
        ws = self.workspace
        return [
            (ws.knowledge_seed_dir, "seed"),
            (os.path.join(ws.knowledge_cache_dir, "github"), "github"),
            (os.path.join(ws.knowledge_cache_dir, "docs"), "docs"),
            (ws.knowledge_uploads_dir, "upload"),
            (ws.examples_dir, "example"),
            (ws.library_dir, "library"),
            (ws.clients_dir, "client"),
        ]

    # ------------------------------------------------------------------ build
    def build(self, force=False):
        self.docs = {}
        for root, source in self.roots():
            if not os.path.isdir(root):
                continue
            for path in _walk(root):
                doc = self._load_doc(path, source, root)
                if doc:
                    self.docs[doc.doc_id] = doc
        self._index()
        self.built_at = time.time()
        return self

    def _load_doc(self, path, source, root):
        ext = os.path.splitext(path)[1].lower()
        if ext not in TEXT_EXTENSIONS and ext not in JSON_EXTENSIONS:
            return None
        try:
            if os.path.getsize(path) > MAX_FILE_BYTES:
                return None
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                raw = handle.read()
        except OSError:
            return None

        rel = os.path.relpath(path, self.workspace.root)
        doc_id = rel.replace(os.sep, "/")
        title = os.path.basename(path)
        kind = "reference"
        tags = []
        meta = {}

        if ext in JSON_EXTENSIONS:
            try:
                payload = json.loads(raw)
            except ValueError:
                return None
            kind, tags, meta, title = _classify_json(payload, title)
            raw = _json_to_text(payload)
        else:
            heading = re.search(r"^#\s+(.+)$", raw, re.M)
            if heading:
                title = heading.group(1).strip()
            if "dql" in doc_id.lower() or "```dql" in raw.lower():
                tags.append("dql")

        tags.extend(_tags_from_path(doc_id))
        return KnowledgeDoc(
            doc_id=doc_id, title=title, source=source, kind=kind, path=rel,
            text=raw, tags=sorted(set(tags)), meta=meta,
        )

    def _index(self):
        self._df = {}
        self._postings = {}
        self._lengths = {}
        for doc_id, doc in self.docs.items():
            tokens = tokenize(doc.title) * 3 + tokenize(" ".join(doc.tags)) * 3 + tokenize(doc.text)
            counts = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            self._lengths[doc_id] = max(1, len(tokens))
            for token, count in counts.items():
                self._df[token] = self._df.get(token, 0) + 1
                self._postings.setdefault(token, []).append((doc_id, count))
        if self._lengths:
            self._avg_len = sum(self._lengths.values()) / float(len(self._lengths))

    # ----------------------------------------------------------------- search
    def search(self, query, limit=8, sources=None, kinds=None, k1=1.4, b=0.75):
        if not self.docs:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        total = len(self.docs)
        scores = {}
        for token in tokens:
            postings = self._postings.get(token)
            if not postings:
                continue
            idf = math.log(1 + (total - len(postings) + 0.5) / (len(postings) + 0.5))
            for doc_id, freq in postings:
                length = self._lengths.get(doc_id, 1)
                denom = freq + k1 * (1 - b + b * length / self._avg_len)
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * (freq * (k1 + 1)) / denom

        hits = []
        for doc_id, score in scores.items():
            doc = self.docs[doc_id]
            if sources and doc.source not in sources:
                continue
            if kinds and doc.kind not in kinds:
                continue
            hits.append(SearchHit(doc=doc, score=score, snippet=_snippet(doc.text, tokens)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    # ------------------------------------------------------------------ utils
    def dashboards(self, sources=None):
        out = []
        for doc in self.docs.values():
            if doc.kind != "dashboard":
                continue
            if sources and doc.source not in sources:
                continue
            out.append(doc)
        return sorted(out, key=lambda d: d.path)

    def stats(self):
        by_source = {}
        by_kind = {}
        for doc in self.docs.values():
            by_source[doc.source] = by_source.get(doc.source, 0) + 1
            by_kind[doc.kind] = by_kind.get(doc.kind, 0) + 1
        return {
            "documents": len(self.docs),
            "terms": len(self._df),
            "bySource": by_source,
            "byKind": by_kind,
            "builtAt": self.built_at,
        }

    def save(self, path=None):
        path = path or os.path.join(self.workspace.state_dir, "kb-index.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "builtAt": self.built_at,
            "documents": [doc.to_meta() for doc in self.docs.values()],
            "stats": self.stats(),
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return path


# --------------------------------------------------------------------- helpers
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def _walk(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            yield os.path.join(base, name)


def _tags_from_path(doc_id):
    parts = re.split(r"[/_\-.]+", doc_id.lower())
    keep = {
        "kubernetes", "k8s", "logs", "log", "spans", "traces", "tracing", "rum",
        "frontend", "hosts", "host", "services", "service", "problems", "davis",
        "security", "vulnerabilities", "bizevents", "business", "costs", "dps",
        "billing", "synthetic", "database", "aws", "azure", "gcp", "network",
        "slo", "alerting", "dql", "segments", "dashboards", "notebooks",
    }
    return [p for p in parts if p in keep]


def _classify_json(payload, fallback_title):
    tags = []
    meta = {}
    title = fallback_title
    if isinstance(payload, dict):
        content = payload.get("content") if isinstance(payload.get("content"), dict) else None
        probe = content or payload
        if isinstance(probe, dict) and isinstance(probe.get("tiles"), dict):
            title = payload.get("name") or fallback_title
            meta = {
                "tiles": len(probe.get("tiles") or {}),
                "variables": len(probe.get("variables") or []),
                "contentVersion": probe.get("version"),
                "format": "platform",
            }
            tags.append("dashboard")
            return "dashboard", tags, meta, title
        if isinstance(payload.get("dashboardMetadata"), dict):
            title = payload["dashboardMetadata"].get("name") or fallback_title
            meta = {"format": "classic", "tiles": len(payload.get("tiles") or [])}
            tags.extend(["dashboard", "classic"])
            return "dashboard", tags, meta, title
        if payload.get("dtdash") or payload.get("spec"):
            return "requirement", ["spec"], {}, payload.get("name") or fallback_title
    return "other", tags, meta, title


def _json_to_text(payload, depth=0):
    """Serializa JSON em texto legivel para indexacao (chaves + valores string)."""

    if depth > 8:
        return ""
    if isinstance(payload, dict):
        parts = []
        for key, value in payload.items():
            parts.append(str(key))
            parts.append(_json_to_text(value, depth + 1))
        return " ".join(p for p in parts if p)
    if isinstance(payload, list):
        return " ".join(_json_to_text(v, depth + 1) for v in payload[:200])
    if isinstance(payload, str):
        return payload
    return ""


def _snippet(text, tokens):
    lowered = strip_accents((text or "").lower())
    best = -1
    for token in tokens:
        pos = lowered.find(token)
        if pos >= 0 and (best < 0 or pos < best):
            best = pos
    if best < 0:
        return (text or "")[:SNIPPET_CHARS].strip()
    start = max(0, best - SNIPPET_CHARS // 3)
    return re.sub(r"\s+", " ", (text or "")[start:start + SNIPPET_CHARS]).strip()
