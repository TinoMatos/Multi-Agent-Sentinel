```yaml
ferramentas_obrigatorias:
  - grafana.list_alerts        # alertas ativos sao o sinal mais forte

limites:
  max_etapas: 4
  limite_tempo_segundos: 60    # SENTINEL_OBS_TIMEOUT_S (agents/triagem.py:79)
  chamadas_ferramenta:
    grafana.list_alerts: 1
    grafana.query_prometheus: 3
    grafana.get_dashboard: 2
    total: 5

acoes_sensiveis: []            # somente leitura

politicas:
  - so roda se GRAFANA_URL E GRAFANA_API_KEY E OPENROUTER_API_KEY existem
  - sem Grafana real, Triagem capa confianca em 70% (degradado)
  - se timeout estourar, fallback deterministico le grafana_alert_id ja salvos no Mongo
  - saida: lista JSON pura na ULTIMA mensagem (sem markdown, sem ```json)
  - maximo 5 itens
```
