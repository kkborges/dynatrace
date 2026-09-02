# dtdash — Dynatrace Dashboard Builder

Ferramenta (CLI + interface web) que recebe **a descricao de uma necessidade em
linguagem natural**, planeja um dashboard da plataforma Dynatrace (Grail / app
Dashboards), mostra uma **previa para analise e aprovacao** e, uma vez aprovado,
**cria o dashboard e os segments diretamente no tenant** do solicitante — salvando
depois uma copia reutilizavel na biblioteca de templates.

```
descricao  ->  planejamento  ->  previa/aprovacao  ->  criacao no tenant  ->  template reutilizavel
   (voce)      (conhecimento         (HTML)            (Document API +        (dashboards/clients)
                Dynatrace +                             Filter Segments)
                capacidades do tenant)
```

* **Sem dependencias externas** — apenas a biblioteca padrao do Python 3.9+.
* **Fontes de conhecimento**: documentacao Dynatrace, repositorios oficiais no
  GitHub (`Dynatrace/dynatrace-for-ai`, `dynatrace-configuration-as-code-samples`,
  `snippets`), pasta local de exemplos e arquivos enviados pelo usuario.
* **Segments** sao derivados da descricao e aplicados ao dashboard.
* **DPS/Grail**: quando o tenant consome DPS, a ferramenta habilita analises por
  logs/Grail e tiles de consumo, sempre em DQL.

---

## 1. Instalacao

```bash
git clone <este-repositorio> && cd dynatrace
./dtdash init
```

Nao ha `pip install` obrigatorio. Opcionalmente:

```bash
pip install -e .      # disponibiliza o comando `dtdash` no PATH
```

## 2. Conectar um tenant

Crie um **platform token** (`dt0s16...`) ou um **OAuth client** no Dynatrace com
os escopos abaixo e exporte a credencial:

```bash
# opcao A - platform token (mais simples)
export DT_PLATFORM_TOKEN='dt0s16.XXXX.YYYY'
./dtdash tenants add --name acme --environment-id abc12345 --client "Acme S.A."

# opcao B - OAuth client credentials
export DT_OAUTH_CLIENT_ID='dt0s02.XXXX'
export DT_OAUTH_CLIENT_SECRET='dt0s02.XXXX.YYYY'
./dtdash tenants add --name acme --environment-id abc12345 --auth oauth \
    --account-urn 'urn:dtaccount:00000000-0000-0000-0000-000000000000'

./dtdash tenants test acme
```

Escopos necessarios:

| Finalidade | Escopos |
|---|---|
| Criar/ler dashboards | `document:documents:read`, `document:documents:write`, `document:documents:delete` |
| Compartilhar com o ambiente | `document:environment-shares:write` |
| Segments | `storage:filter-segments:read`, `:write`, `:share` |
| Consultar dados (DQL) | `storage:logs:read`, `storage:metrics:read`, `storage:events:read`, `storage:spans:read`, `storage:bizevents:read`, `storage:entities:read`, `storage:system:read`, `storage:user.sessions:read`, `storage:user.events:read`, `storage:security.events:read`, `storage:buckets:read` |

Nenhum segredo e gravado no repositorio: a configuracao guarda apenas o **nome da
variavel de ambiente** que contem a credencial.

## 3. Base de conhecimento

```bash
./dtdash kb sync         # baixa docs Dynatrace + repositorios oficiais do GitHub
./dtdash kb add ./meus-dashboards-exemplo
./dtdash kb search "web vitals"
./dtdash kb status
```

A base ja vem com um nucleo (`knowledge/seed/`) destilado da documentacao oficial:
schema de dashboards, variaveis, DQL, segments, APIs de plataforma, DPS/Grail e um
playbook de design.

## 4. Gerar, revisar e publicar

```bash
# 1) planejar (nada e criado no tenant)
./dtdash plan "Dashboard para o time de SRE acompanhar a saude dos servicos de \
pagamento em producao: taxa de erro, latencia p90, problemas ativos do Davis e \
erros de log no namespace pagamentos das ultimas 24 horas" -t acme --validate-live

# ou a partir de um arquivo
./dtdash plan --file examples/requirements/01-sre-servicos-producao.md -t acme

# 2) revisar a previa (HTML) e o JSON
./dtdash preview --path        # caminho do HTML
./dtdash preview --json        # JSON do dashboard

# 3) aprovar -> cria segments + dashboard no tenant e salva o template
./dtdash approve --yes --share
```

A saida de `approve` traz o id do documento, a URL do dashboard
(`https://<env>.apps.dynatrace.com/ui/apps/dynatrace.dashboards/dashboard/<id>`),
os uids dos segments criados e o caminho do template salvo.

### Interface web

```bash
./dtdash serve            # http://127.0.0.1:8080
```

A interface cobre o fluxo completo: descrever, gerar previa, revisar, aprovar (ou
simular/rejeitar), navegar na biblioteca de templates, sincronizar o conhecimento
e enviar arquivos de exemplo.

> Ao expor o servidor fora de `127.0.0.1`, defina `DTDASH_WEB_TOKEN` — o servidor
> passa a exigir o header `X-Dtdash-Token`.

## 5. Validar contra um tenant real (`selftest`)

Antes de confiar o fluxo a um cliente, rode a bateria de verificacao. Ela executa
as chamadas **na mesma ordem em que a publicacao as usa** e diz, uma a uma, se a
API respondeu como a documentacao descreve:

```bash
./dtdash selftest -t acme                 # somente leitura (nao escreve nada)
./dtdash selftest -t acme --write --yes   # inclui criar/remover objetos temporarios
./dtdash selftest -t acme --json          # saida para pipeline de CI
```

| Verificacao | O que prova |
|---|---|
| `config`, `auth` | perfil, credencial e obtencao do token (SSO no caso de OAuth) |
| `documents.read`, `segments.read` | escopos de leitura e formato das listagens |
| `grail.execute` | `query:execute` + `query:poll` com uma DQL sintetica (`data record(...)`, custo zero de scan) |
| `grail.verify` | existencia do `query:verify` (aceita DQL valida, rejeita invalida) |
| `grail.dataobjects` | quais data objects o tenant expoe |
| `grail.dps` | consumo DPS — ausencia vira **aviso**, nunca conclusao de falta de licenca |
| `metrics.catalog` | quais das metricas usadas pelos blueprints existem neste tenant, e quais blueprints ficam afetados |
| `dql.blueprints` | sintaxe das 60 DQL do catalogo validadas pelo proprio tenant |
| `segments.write` * | criacao, leitura e nome do campo do identificador |
| `documents.write` * | criacao do dashboard e round-trip do conteudo |
| `tile.segments` * | se a propriedade `segments` do tile sobrevive ao round-trip (se nao, use `--segment-mode dql`) |
| `documents.share` * | `environment-shares` ou o fallback `PATCH isPrivate` |
| `cleanup` * | remocao dos objetos temporarios (roda mesmo se algo falhar no meio) |

`*` somente com `--write`. Os objetos temporarios usam o prefixo
`dtdash-selftest` e sao removidos ao final; `--no-cleanup` mantem tudo para
inspecao manual. O relatorio tambem fica em `.dtdash/selftest-<tenant>-<data>.json`
e a mesma bateria esta na aba **Diagnostico** da interface web.

Codigo de saida: `0` sem falhas, `2` com falhas — da para usar direto em CI.

## 6. Metricas: Grail (`dt.*`) x classico (`builtin:*`)

Na plataforma Grail as metricas nativas foram renomeadas: o prefixo `builtin:`
virou `dt.` e camelCase virou snake_case
([docs](https://docs.dynatrace.com/docs/analyze-explore-automate/metrics/built-in-metrics-on-grail)).
O catalogo do dtdash usa as chaves Grail, mas **quem decide e o tenant**: antes de
montar os tiles a ferramenta le o indice de metricas e classifica cada chave.

| Situacao | O que o dtdash faz |
|---|---|
| a chave `dt.*` existe | usa como esta |
| so existe a equivalente `builtin:*` | reescreve a DQL com a chave classica entre crases |
| nao existe nenhuma das duas | marca o tile como indisponivel e, por padrao, **remove** (`--on-missing keep` mantem) |
| nao foi possivel verificar (sem permissao, indice vazio, offline) | mantem o tile e avisa - nunca conclui que a metrica nao existe |

Isso evita publicar dashboard com tile vazio e faz o mesmo pedido funcionar tanto
em tenant Gen3/DPS quanto em tenant com metricas classicas.

### Permissoes do Grail

Um `403 NOT_AUTHORIZED_FOR_TABLE` significa que falta a permissao de leitura
**daquela tabela** — nao que a metrica ou o dado nao exista. O dtdash sonda cada
tabela e diz qual permissao conceder:

```bash
./dtdash tenants test acme

TABELA               STATUS    PERMISSAO                        DETALHE
logs                 ok        storage:logs:read                1 registro lido
metrics              denied    storage:metrics:read             sem permissao de leitura
smartscape           denied    storage:smartscape:read          sem permissao de leitura

permissoes a conceder: storage:metrics:read, storage:smartscape:read
```

A mesma matriz aparece na previa do dashboard, no `selftest` (`grail.tables`) e na
aba Diagnostico da interface web.

## 7. Biblioteca de dashboards

```
dashboards/
  library/   # templates genericos (reutilizaveis em qualquer cliente)
  clients/
    acme/    # dashboards criados no cliente Acme (com metadados de origem)
  index.json # indice gerado automaticamente
```

Todo dashboard publicado e salvo em `dashboards/clients/<cliente>/` com um bloco
`dtdash` contendo audiencia, dominios, requisitos originais, segments e dados da
publicacao — pronto para reuso:

```bash
./dtdash templates list
./dtdash plan "mesma necessidade para outro cliente" \
    --base dashboards/clients/acme/sre-servicos.json -t outro-cliente
./dtdash templates save --scope library     # promove um template para a biblioteca generica
```

## 8. Comandos

| Comando | Para que serve |
|---|---|
| `dtdash init` | prepara o workspace |
| `dtdash tenants add\|list\|use\|remove\|test` | perfis de tenant e teste de conexao/capacidades |
| `dtdash kb sync\|status\|search\|add` | base de conhecimento |
| `dtdash plan` | gera a proposta + previa |
| `dtdash preview` | mostra a previa (texto, caminho do HTML ou JSON) |
| `dtdash proposals` | lista as propostas |
| `dtdash approve` | cria segments + dashboard no tenant |
| `dtdash reject` | marca a proposta como rejeitada |
| `dtdash templates list\|show\|save\|import\|reindex` | biblioteca de templates |
| `dtdash validate <arquivo.json>` | valida um dashboard (estrutura, visualizacoes, DQL) |
| `dtdash selftest` | verifica as APIs do tenant usadas pelo dtdash |
| `dtdash catalog` | lista os blueprints de tile disponiveis |
| `dtdash serve` | interface web |
| `dtdash doctor` | diagnostico do ambiente |

Opcoes uteis de `plan`: `--audience exec|sre|dev|finops`, `--segment-mode
tile|dql|both`, `--on-missing drop|keep`, `--max-tiles N`, `--base <template>`,
`--offline`, `--validate-live`, `--domain <dominio>`.

## 9. Como o planejamento funciona

1. **Leitura da necessidade** — separa requisitos, detecta dominios (servicos,
   Kubernetes, logs, problemas, RUM, banco, seguranca, negocio, DPS...), audiencia,
   filtros concretos (namespace, cluster, ambiente...) e janela de tempo.
2. **Capacidades do tenant** — descobre os data objects disponiveis
   (`fetch dt.system.data_objects`) e sonda o consumo DPS
   (`dt.system.events` com `event.kind == "BILLING_USAGE_EVENT"`).
   *Ausencia de eventos de billing nao prova ausencia de licenca* — a ferramenta
   diz isso explicitamente na previa.
3. **Selecao de tiles** — escolhe blueprints do catalogo (`dtdash catalog`), cada um
   com pergunta, DQL e visualizacao compativel com o formato do resultado.
4. **Segments e variaveis** — filtros com valor concreto viram *filter-segments*;
   dimensoes citadas sem valor viram variaveis de dashboard. Filtros so sao
   injetados onde o campo realmente existe.
5. **Verificacao** — o indice de metricas do tenant e lido uma vez e cada chave e
   resolvida (Grail, classica ou ausente); a DQL passa por lint e, com
   `--validate-live`, por `query:verify` + execucao com `limit`.
6. **Previa** — HTML com layout, DQL por tile, segments, variaveis, apontamentos de
   validacao, fontes consultadas e a **matriz de cobertura** (cada necessidade
   declarada x tiles que a respondem).

## 10. Desenvolvimento

```bash
python3 -m unittest discover -s tests -t .
```

Documentacao adicional: [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) e
[`docs/API-DYNATRACE.md`](docs/API-DYNATRACE.md).

## Referencias

- Dashboards da plataforma e Document API — <https://docs.dynatrace.com/docs/analyze-explore-automate/dashboards-and-notebooks/document-api>
- Acesso as APIs de plataforma — <https://developer.dynatrace.com/develop/access-platform-apis-from-outside/>
- Segments — <https://docs.dynatrace.com/docs/manage/segments>
- Skills oficiais (schema de dashboards, DQL, DPS) — <https://github.com/Dynatrace/dynatrace-for-ai>
- Dynatrace Platform Subscription — <https://docs.dynatrace.com/docs/manage/subscriptions-and-licensing/dynatrace-platform-subscription>
