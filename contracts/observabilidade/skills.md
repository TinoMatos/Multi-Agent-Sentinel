```yaml
habilidades:
  - nome: grafana.list_alerts
    descricao: lista alertas ativos (firing) no Grafana
    entrada:
      state: string          # default "firing"
    saida:
      alerts: list

  - nome: grafana.query_prometheus
    descricao: executa query PromQL para spikes de CPU/latencia/error_rate
    entrada:
      query: string
      time_range: string     # ex. "now-1h"
    saida:
      series: list

  - nome: grafana.get_dashboard
    descricao: busca dashboard por uid para correlacionar paineis
    entrada:
      uid: string
    saida:
      dashboard: object
```
