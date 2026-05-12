```yaml
nome: observabilidade
descricao: consulta Grafana MCP para alertas ativos e spikes (CPU, latencia, error_rate) na ultima hora
tipo: task_based

objetivo: correlacionar_sintoma_com_alertas_e_metricas_ao_vivo

contrato_saida:
  formato: json
  campos_obrigatorios:
    - tipo               # sempre "grafana"
    - ref                # alert_id | uid | panel_id
    - nota
  exemplo:
    - { tipo: grafana, ref: "cflbwhpihs7wga", nota: "HTTP 500 spike on Acme login (firing)" }
```

Roda em modelo `fast` (Haiku por default) — barato, executa em todo RCA.
