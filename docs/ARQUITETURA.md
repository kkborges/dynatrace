# Arquitetura do dtdash

```
                        +---------------------------+
  descricao do          |        cli.py / server.py |
  solicitante  ------>  |   (CLI e interface web)   |
                        +-------------+-------------+
                                      |
                              service.py (orquestracao)
                                      |
   +-------------------+--------------+--------------+-------------------+
   |                   |                             |                   |
knowledge/          planner.py                   builder.py          deploy.py
(store, sources)    + catalog.py                 + validator.py      + library.py
   |                   |                             |                   |
docs Dynatrace     DashboardSpec                dashboard JSON       Document API
GitHub oficial     (tiles, variaveis,           (v21, tiles,         Filter Segments
exemplos/uploads    segments, requisitos)        layouts, settings)   templates locais
                                      |
                              capabilities.py + client.py
                              (Grail, data objects, DPS)
```

## Modulos

| Modulo | Responsabilidade |
|---|---|
| `config.py` | workspace, perfis de tenant, resolucao de credenciais por variavel de ambiente |
| `httpclient.py` | HTTP com retry exponencial, multipart e suporte a proxy/CA |
| `auth.py` | platform token e OAuth client credentials (com cache de token) |
| `client.py` | Document API, Filter Segments, Grail Query API, descoberta de data objects |
| `capabilities.py` | sonda o tenant: data objects, Grail consultavel, consumo DPS (tri-estado) |
| `knowledge/` | indice BM25 sobre docs, repositorios GitHub, exemplos e uploads |
| `catalog.py` | blueprints de tile (pergunta + DQL + visualizacao + metadados) |
| `planner.py` | descricao -> `DashboardSpec` (dominios, audiencia, filtros, segments, variaveis) |
| `spec.py` | modelo intermediario serializavel |
| `builder.py` | `DashboardSpec` -> JSON da plataforma (v21) e o caminho inverso |
| `validator.py` | estrutura, grade, variaveis, compatibilidade visualizacao/query, lint de DQL, validacao ao vivo |
| `preview.py` | previa HTML e resumo em texto |
| `proposals.py` | ciclo de vida da proposta (pendente / aprovado / rejeitado / publicado) |
| `deploy.py` | segments -> dashboard -> compartilhamento -> template |
| `library.py` | biblioteca `dashboards/library` e `dashboards/clients` + indice |
| `service.py` | orquestra o fluxo para CLI e web |

## Decisoes de projeto

**Sem dependencias externas.** Tudo roda com a biblioteca padrao — a ferramenta
precisa funcionar em ambientes de cliente restritos, sem instalar pacotes.

**Blueprints em vez de geracao livre de DQL.** Cada tile vem de um blueprint com
DQL escrita a partir dos padroes oficiais (skills `Dynatrace/dynatrace-for-ai`).
Isso evita inventar campos e metricas, que e o erro mais comum ao gerar dashboards
automaticamente. A adaptacao ao pedido acontece na **selecao**, no **filtro** e no
**layout**, nao na invencao de sintaxe.

**Injecao de filtro consciente do modelo de dados.**
Em modelos de registro (logs, spans, eventos) o campo existe no esquema e o filtro
e sempre seguro. Em metricas e smartscape o filtro so entra quando a dimensao ja
aparece na query — evitando filtrar, por exemplo, pods por nome de servico.

**Segments com duas estrategias.** `--segment-mode tile` usa a propriedade
`segments` do tile (nativa da plataforma); `dql` embute o filtro na query (funciona
em qualquer versao); `both` aplica as duas.

**DPS tri-estado.** `dps = True | False | None`. Eventos de billing medem consumo,
nao entitlement — a ferramenta nunca afirma que falta licenca.

**Aprovacao explicita.** `plan` nunca escreve no tenant. Somente `approve`
(com confirmacao ou `--yes`) cria segments e dashboard.

## Ciclo de vida da proposta

```
plan  ->  .dtdash/proposals/<id>/{spec.json, dashboard.json, preview.html, report.json, meta.json}
             |                         |
          reject                    approve  ->  deployment.json + dashboards/clients/<cliente>/<slug>.json
```

## Extensao

Adicionar um novo tipo de tile = adicionar um `Blueprint` em `catalog.py`:

```python
Blueprint(
    bp_id="services.apdex",
    domain="services", signal="latency",
    title="Apdex por servico",
    question="A experiencia esta dentro do alvo?",
    query="timeseries ...",
    visualization="table", source_kind="timeseries", filter_object="metrics",
    width=12, height=8, section="Servicos",
    metrics=["dt.service.request.response_time"],
    keywords=["apdex", "satisfacao", "experiencia"],
    priority=60,
)
```

O planner passa a considera-lo automaticamente (selecao por dominio, audiencia,
palavras-chave e capacidades do tenant) e o validador cobre a nova query.
