"""Ingestao de fontes de conhecimento.

Fontes suportadas
-----------------
* GitHub oficial Dynatrace (clone raso, apenas caminhos relevantes)
* Documentacao Dynatrace / Community (download de paginas publicas)
* Pasta local de exemplos (``examples/``) e uploads do usuario
"""

import fnmatch
import html
import json
import os
import re
import shutil
import subprocess
import time

from .. import httpclient

# ------------------------------------------------------------------ catalogos

DEFAULT_GITHUB_SOURCES = [
    {
        "name": "dynatrace-for-ai",
        "url": "https://github.com/Dynatrace/dynatrace-for-ai.git",
        "description": "Skills oficiais Dynatrace: schema de dashboards, DQL, semantic dictionary, DPS.",
        "include": ["skills/**", "prompts/**", "*.md", "llms.txt"],
        "enabled": True,
    },
    {
        "name": "config-as-code-samples",
        "url": "https://github.com/Dynatrace/dynatrace-configuration-as-code-samples.git",
        "description": "Exemplos oficiais de configuracao como codigo, incluindo dashboards de plataforma.",
        "include": ["**/dashboards/**", "**/*.md"],
        "enabled": True,
    },
    {
        "name": "snippets",
        "url": "https://github.com/Dynatrace/snippets.git",
        "description": "Snippets oficiais (dashboards, APIs, DQL).",
        "include": ["product/**", "api/**", "*.md"],
        "enabled": True,
    },
    {
        "name": "config-as-code",
        "url": "https://github.com/Dynatrace/dynatrace-configuration-as-code.git",
        "description": "Monaco - documentacao de deploy de dashboards/segments como codigo.",
        "include": ["documentation/**", "*.md"],
        "enabled": False,
    },
]

DEFAULT_DOC_SOURCES = [
    {
        "name": "dashboards-new",
        "url": "https://docs.dynatrace.com/docs/analyze-explore-automate/dashboards-and-notebooks/dashboards-new",
        "enabled": True,
    },
    {
        "name": "document-api",
        "url": "https://docs.dynatrace.com/docs/analyze-explore-automate/dashboards-and-notebooks/document-api",
        "enabled": True,
    },
    {
        "name": "segments",
        "url": "https://docs.dynatrace.com/docs/manage/segments",
        "enabled": True,
    },
    {
        "name": "dql-commands",
        "url": "https://docs.dynatrace.com/docs/platform/grail/dynatrace-query-language/commands",
        "enabled": True,
    },
    {
        "name": "dps-subscription",
        "url": "https://docs.dynatrace.com/docs/manage/subscriptions-and-licensing/dynatrace-platform-subscription",
        "enabled": True,
    },
    {
        "name": "access-platform-apis",
        "url": "https://developer.dynatrace.com/develop/access-platform-apis-from-outside/",
        "enabled": True,
    },
]


class SyncResult(object):
    def __init__(self):
        self.ok = []
        self.failed = []
        self.skipped = []
        self.files = 0

    def to_dict(self):
        return {
            "ok": self.ok,
            "failed": self.failed,
            "skipped": self.skipped,
            "files": self.files,
        }


class KnowledgeSync(object):
    def __init__(self, workspace, transport=None, runner=None):
        self.workspace = workspace
        self._transport = transport or httpclient.request
        self._runner = runner or _run

    # ------------------------------------------------------------------ github
    def sync_github(self, sources=None, only=None, timeout=600):
        sources = sources or DEFAULT_GITHUB_SOURCES
        dest_root = os.path.join(self.workspace.knowledge_cache_dir, "github")
        os.makedirs(dest_root, exist_ok=True)
        result = SyncResult()

        for source in sources:
            name = source["name"]
            if only and name not in only:
                continue
            if not source.get("enabled", True) and not (only and name in only):
                result.skipped.append(name)
                continue
            dest = os.path.join(dest_root, name)
            try:
                if os.path.isdir(os.path.join(dest, ".git")):
                    self._runner(["git", "-C", dest, "fetch", "--depth", "1", "origin"], timeout)
                    self._runner(["git", "-C", dest, "reset", "--hard", "FETCH_HEAD"], timeout)
                else:
                    shutil.rmtree(dest, ignore_errors=True)
                    self._runner(
                        ["git", "clone", "--depth", "1", "--quiet", source["url"], dest],
                        timeout,
                    )
                kept = _prune(dest, source.get("include"))
                result.files += kept
                result.ok.append({"name": name, "files": kept, "path": dest})
            except Exception as exc:  # noqa: BLE001 - reportamos a falha
                result.failed.append({"name": name, "error": str(exc)})
        _write_manifest(dest_root, sources, result)
        return result

    # -------------------------------------------------------------------- docs
    def sync_docs(self, sources=None, only=None):
        sources = sources or DEFAULT_DOC_SOURCES
        dest = os.path.join(self.workspace.knowledge_cache_dir, "docs")
        os.makedirs(dest, exist_ok=True)
        result = SyncResult()
        for source in sources:
            name = source["name"]
            if only and name not in only:
                continue
            if not source.get("enabled", True):
                result.skipped.append(name)
                continue
            try:
                response = self._transport("GET", source["url"], headers={"Accept": "text/html"})
                if not response.ok:
                    raise RuntimeError("HTTP %s" % response.status)
                text = html_to_text(response.text)
                if len(text) < 200:
                    raise RuntimeError("conteudo vazio ou bloqueado")
                path = os.path.join(dest, "%s.md" % name)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("# %s\n\nFonte: %s\n\n%s\n" % (name, source["url"], text))
                result.ok.append({"name": name, "path": path, "chars": len(text)})
                result.files += 1
            except Exception as exc:  # noqa: BLE001
                result.failed.append({"name": name, "error": str(exc)})
        return result

    # ----------------------------------------------------------------- uploads
    def add_upload(self, filename, data, subdir=""):
        """Grava um arquivo enviado pelo usuario na pasta de uploads."""

        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(filename or "upload"))
        if not safe:
            safe = "upload"
        target_dir = os.path.join(self.workspace.knowledge_uploads_dir, subdir or "")
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, safe)
        mode = "wb" if isinstance(data, (bytes, bytearray)) else "w"
        kwargs = {} if mode == "wb" else {"encoding": "utf-8"}
        with open(path, mode, **kwargs) as handle:
            handle.write(data)
        return path

    def import_path(self, source_path, subdir="imported"):
        """Copia um arquivo ou diretorio local para a base de conhecimento."""

        source_path = os.path.abspath(source_path)
        target_dir = os.path.join(self.workspace.knowledge_uploads_dir, subdir)
        os.makedirs(target_dir, exist_ok=True)
        if os.path.isdir(source_path):
            target = os.path.join(target_dir, os.path.basename(source_path.rstrip(os.sep)))
            if os.path.isdir(target):
                shutil.rmtree(target)
            shutil.copytree(source_path, target)
        else:
            target = os.path.join(target_dir, os.path.basename(source_path))
            shutil.copy2(source_path, target)
        return target


# --------------------------------------------------------------------- helpers
def _run(cmd, timeout):
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False
    )
    if proc.returncode != 0:
        output = (proc.stdout or b"").decode("utf-8", "replace")[-400:]
        raise RuntimeError("comando falhou (%s): %s" % (" ".join(cmd[:3]), output.strip()))
    return proc


def _prune(root, include_globs):
    """Remove arquivos fora dos padroes desejados; devolve quantos ficaram."""

    if not include_globs:
        return sum(1 for _ in _iter_files(root))
    kept = 0
    for path in list(_iter_files(root)):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if any(_match(rel, pattern) for pattern in include_globs):
            kept += 1
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    _remove_empty_dirs(root)
    return kept


def _match(rel, pattern):
    if fnmatch.fnmatch(rel, pattern):
        return True
    if pattern.endswith("/**"):
        return rel.startswith(pattern[:-3] + "/")
    if pattern.startswith("**/"):
        return fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(
            os.path.basename(rel), pattern[3:]
        ) or ("/" + pattern[3:].rstrip("*/") in "/" + rel)
    return False


def _iter_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            yield os.path.join(base, name)


def _remove_empty_dirs(root):
    for base, dirs, files in os.walk(root, topdown=False):
        if ".git" in base:
            continue
        if not dirs and not files and os.path.abspath(base) != os.path.abspath(root):
            try:
                os.rmdir(base)
            except OSError:
                pass


def _write_manifest(dest_root, sources, result):
    manifest = {
        "syncedAt": time.time(),
        "sources": [
            {k: v for k, v in s.items() if k in ("name", "url", "description", "enabled")}
            for s in sources
        ],
        "result": result.to_dict(),
    }
    with open(os.path.join(dest_root, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style|nav|footer|svg)[^>]*>.*?</\1>", re.S | re.I)


def html_to_text(markup):
    text = _SCRIPT_RE.sub(" ", markup or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|li|h[1-6]|tr)>", "\n", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()
