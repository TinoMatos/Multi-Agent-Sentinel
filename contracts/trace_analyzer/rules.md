```yaml
ferramentas_obrigatorias:
  - carregar_traces        # ler todos os trace_*.json da pasta

limites:
  max_etapas: 3            # carregar + agregar + renderizar
  limite_tempo_segundos: 10
  chamadas_ferramenta:
    carregar_traces: 1
    agregar_kpis: 1
    renderizar_relatorio: 1
    total: 3

acoes_sensiveis: []        # somente leitura — nao escreve em Mongo, reports/ ou traces/

politicas:
  - pasta data/traces/ inexistente NAO eh erro (retorna KPIs zeradas)
  - trace JSON corrompido eh ignorado silenciosamente (try/except por arquivo)
  - cliente ausente vira "desconhecido" no agrupamento
  - motivo de veto truncado em 80 chars para agrupar variacoes do mesmo motivo
```
