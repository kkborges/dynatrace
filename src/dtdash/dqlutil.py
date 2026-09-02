"""Utilitarios de manipulacao de DQL (injecao de filtros, lint leve)."""

import re

TIMESERIES_START = re.compile(r"^\s*timeseries\b", re.I)
FETCH_START = re.compile(r"^\s*(fetch|data|load)\b", re.I)
SMARTSCAPE_START = re.compile(r"^\s*smartscape(Nodes|Edges)\b", re.I)


def detect_source_kind(query):
    first = (query or "").strip().splitlines()[0] if (query or "").strip() else ""
    if TIMESERIES_START.match(first):
        return "timeseries"
    if SMARTSCAPE_START.match(first):
        return "smartscape"
    if FETCH_START.match(first):
        return "fetch"
    return "none"


def _command_block_end(lines):
    """Indice da primeira linha que comeca com '|' (fim do comando inicial)."""

    for index, line in enumerate(lines):
        if line.lstrip().startswith("|"):
            return index
    return len(lines)


def inject_filters(query, expressions, source_kind=None):
    """Adiciona expressoes de filtro a uma query preservando a semantica.

    * ``timeseries`` -> parametro ``filter: { ... }`` do proprio comando
    * ``fetch``/``smartscape`` -> nova etapa ``| filter ...`` logo apos a origem
    """

    expressions = [e.strip() for e in (expressions or []) if e and e.strip()]
    if not expressions or not query:
        return query
    kind = source_kind or detect_source_kind(query)
    expr = " and ".join("(%s)" % e if " or " in e.lower() else e for e in expressions)
    lines = query.rstrip().splitlines()
    if not lines:
        return query

    if kind == "timeseries":
        end = _command_block_end(lines)
        block = lines[:end]
        if not block:
            return query
        last = block[-1].rstrip()
        if re.search(r"filter\s*:\s*\{", last):
            # ja existe um filtro no comando: combina com 'and'
            block[-1] = re.sub(
                r"filter\s*:\s*\{(.*?)\}",
                lambda m: "filter: {%s and %s}" % (m.group(1).strip(), expr),
                last,
                count=1,
                flags=re.S,
            )
        else:
            block[-1] = "%s, filter: { %s }" % (last.rstrip(","), expr)
        return "\n".join(block + lines[end:])

    if kind in ("fetch", "smartscape"):
        end = _command_block_end(lines)
        head = lines[:end]
        tail = lines[end:]
        return "\n".join(head + ["| filter %s" % expr] + tail)

    return "%s\n| filter %s" % (query, expr)


def quote(value):
    """Escapa um valor string para uso literal em DQL."""

    return '"%s"' % str(value).replace("\\", "\\\\").replace('"', '\\"')


def equals(field_name, value):
    return "%s == %s" % (field_name, quote(value))


def in_values(field_name, values):
    if len(values) == 1:
        return equals(field_name, values[0])
    return "in(%s, {%s})" % (field_name, ", ".join(quote(v) for v in values))


def variable_filter(field_name, variable_key, multiple=False):
    if multiple:
        return "in(%s, array($%s))" % (field_name, variable_key)
    return "%s == $%s" % (field_name, variable_key)


# ------------------------------------------------------------------ lint leve
LINT_RULES = [
    (re.compile(r"\bfilter\s+[\w.]+\s+in\s*\["), 
     "use in(campo, {\"a\",\"b\"}) - colchetes delimitam subquery, nao array literal"),
    (re.compile(r"\blog\.level\b"),
     "campo de severidade de log e 'loglevel' (ou 'status'), nao 'log.level'"),
    (re.compile(r"\bmetrics\s+dt\.[\w.]+"),
     "'metrics' retorna metadados; para valores use 'timeseries agg(metrica)'"),
    (re.compile(r"\btoLowercase\s*\("),
     "a funcao correta e lower()"),
    (re.compile(r"\blength\s*\("),
     "para tamanho de string use stringLength()"),
    (re.compile(r"\bfetch\s+dt\.metric\b"),
     "nao existe 'fetch dt.metric' - use 'timeseries'"),
    (re.compile(r"(?<![=!<>])=(?![=~])(?=[^=]*?\bfilter\b)"), None),  # placeholder
]


def lint(query):
    """Retorna uma lista de avisos de sintaxe conhecidos."""

    warnings = []
    if not query:
        return warnings
    for pattern, message in LINT_RULES:
        if message and pattern.search(query):
            warnings.append(message)

    if re.search(r"\bfilter\s+[\w.`]+\s*=\s*[^=]", query):
        warnings.append("DQL usa '==' para igualdade; '=' e atribuicao")

    if re.search(r"\bby\s*:\s*[a-zA-Z]", query):
        warnings.append("a clausula by: exige chaves: by:{campo}")

    if re.search(r"\bpercentile\s*\(", query) and re.match(r"^\s*timeseries", query.strip()) \
            and "rollup" not in query and "scalar" not in query:
        # percentile em metricas gauge normalmente exige rollup
        pass

    if re.search(r"\bsort\s+count\(\)", query):
        warnings.append("campos com parenteses precisam de crase: sort `count()` desc")

    if re.search(r"\bfetch\s+spans\b", query) and re.search(r"\bbin\(\s*timestamp", query):
        warnings.append("spans nao tem 'timestamp'; use start_time/end_time")

    return warnings
