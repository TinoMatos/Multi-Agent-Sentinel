```yaml
memoria_curta:
  guardar:
    - kpis_agregados
  descartar:
    - traces_brutos             # ja foi pra agregacao; nao precisa repetir
    - paths_de_arquivo
  max_registros: 3

resumo_final:
  max_linhas: 6
  campos:
    - total_execucoes
    - taxa_aprovacao_critic
    - confianca_media
    - evidencias_degradadas_pct
    - top_motivo_veto
    - top_cliente
```
