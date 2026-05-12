```yaml
memoria_curta:
  guardar:
    - cliente
    - ticket
    - erros
    - rcas_similares
  descartar:
    - queries_mongo_completas
    - documentos_brutos_repetidos    # _id em vez do doc inteiro
  max_registros: 15

resumo_final:
  max_linhas: 4
  campos:
    - cliente_nome
    - ticket_descricao
    - qtde_erros_correlacionados
    - qtde_rcas_historicos
```
