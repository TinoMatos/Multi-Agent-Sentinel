```yaml
habilidades:
  - nome: carregar_traces
    descricao: le todos os trace_*.json em data/traces/ (ignora corrompidos)
    entrada:
      traces_dir: string
    saida:
      traces: list

  - nome: agregar_kpis
    descricao: calcula taxa de aprovacao, confianca media, evidencias degradadas, agrupamentos
    entrada:
      traces: list
    saida:
      kpis: object

  - nome: renderizar_relatorio
    descricao: monta markdown com cabecalho, KPIs, agrupamentos e motivos de veto
    entrada:
      kpis: object
    saida:
      markdown: string
```
