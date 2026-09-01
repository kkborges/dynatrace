# Variaveis de dashboard (filtros dinamicos)

Fonte: `Dynatrace/dynatrace-for-ai` -> `skills/dt-app-dashboards/references/variables.md`.

Definidas em `content.variables` e referenciadas nas queries como `$Chave`.

```json
{ "version": 2, "key": "Servico", "type": "query", "visible": true,
  "editable": true, "multiple": false,
  "input": "smartscapeNodes SERVICE | fields name | sort name asc" }
```

Tipos: `query` (DQL), `csv` (lista fixa), `text` (livre).

Regras que evitam dashboards quebrados:

- a query da variavel precisa devolver **exatamente um campo** e **pelo menos
  uma linha**;
- para valores distintos use `dedup campo`, nunca `summarize by:{campo}` sem
  agregacao;
- filtre vazios: `| filter isNotNull(campo) and campo != ""`;
- toda variavel declarada tem que ser usada em pelo menos um tile;
- `version: 2` para variaveis novas (aceita `fetch`, `expand`, `summarize`).

## Uso nas queries

| Configuracao | Padrao na query |
|---|---|
| `multiple: false` | `filter campo == $Var` |
| `multiple: true`  | `filter in(campo, array($Var))` |

Modificadores:

| Modificador | Para que serve | Exemplo |
|---|---|---|
| (padrao) | igualdade de string / multi-select | `filter service.name == $Servico` |
| `:noquote` | numeros e duracoes | `limit $N:noquote`, `bin(timestamp, $Bin:noquote)` |
| `:backtick` | nome de campo em `by:{}` / `sort` | `summarize count(), by:{$GroupBy:backtick}` |
| `:triplequote` | constantes string em `matchesPhrase()`/`contains()` | `matchesPhrase(content, $Busca:triplequote)` |

Valores padrao:

- `multiple: true` -> `"defaultValue": "3420b2ac-f1cf-4b24-b62d-61ba1ba8ed05*"`
  (token magico "selecionar tudo");
- `multiple: false` -> omitir `defaultValue` (o primeiro valor e escolhido);
- `text` -> omitir ou `""` (nunca `"*"`).

Variaveis podem depender de outras (`Namespace` filtrando por `$Cluster`), desde
que nao haja ciclo.
