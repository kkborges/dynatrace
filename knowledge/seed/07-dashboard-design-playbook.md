# Playbook de design de dashboards (pratica de campo Dynatrace)

## 1. Descubra a pergunta antes do tile

Todo dashboard responde a perguntas. Escreva-as e so entao escolha os tiles.
Um tile que nao responde a uma pergunta declarada e ruido.

## 2. Estrutura em tres camadas

1. **Cabecalho / KPIs** (`singleValue`, `meterBar`): estado atual em 5 segundos.
2. **Tendencias** (`lineChart`, `areaChart`): o que mudou no periodo.
3. **Detalhe / drill-down** (`table`, `categoricalBarChart`, `honeycomb`):
   onde investigar.

## 3. Sinais de ouro (Google SRE) mapeados no Dynatrace

| Sinal | Onde buscar |
|---|---|
| Latencia | `dt.service.request.response_time`, `fetch spans` (percentis) |
| Trafego | `dt.service.request.count`, `fetch spans \| summarize count()` |
| Erros | `dt.service.request.failure_count`, logs `loglevel`, `dt.davis.problems` |
| Saturacao | `dt.host.cpu.usage`, `dt.host.memory.usage`, limites de CPU/memoria K8s |

## 4. Audiencia muda o layout

| Audiencia | O que priorizar |
|---|---|
| Executivo / negocio | poucos KPIs, tendencia, disponibilidade, impacto no negocio |
| SRE / operacao | sinais de ouro, problemas abertos, saturacao, drill-down por entidade |
| Desenvolvimento | erros por servico/endpoint, latencia por operacao, logs de excecao |
| FinOps / plataforma | consumo DPS, volume de ingestao, custo de query por origem |

## 5. Regras que evitam retrabalho

- Nao fixe intervalo de tempo dentro das queries - o seletor do dashboard manda.
- Toda variavel declarada precisa ser usada em algum tile.
- Prefira segments a repetir o mesmo `filter` em 12 tiles.
- Valide toda DQL antes de publicar (`query:verify` e uma execucao com `limit`).
- Nomeie tiles com a pergunta que respondem ("Servicos com maior taxa de erro"),
  nao com o nome da metrica.
- Limite tabelas (`limit 20`) e ordene pelo que importa.
- Documente o dashboard com um tile markdown de cabecalho: dono, objetivo,
  como agir quando um numero sai da faixa.
