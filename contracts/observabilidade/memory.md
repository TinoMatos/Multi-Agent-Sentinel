```yaml
memoria_curta:
  guardar:
    - pergunta
    - alertas_firing
    - spikes_correlacionados
  descartar:
    - series_temporais_brutas    # so a interpretacao importa, nao os datapoints
    - dashboards_completos
  max_registros: 8

resumo_final:
  max_linhas: 3
  campos:
    - qtde_alertas_firing
    - qtde_spikes
    - modo                       # "live" | "degradado"
```
