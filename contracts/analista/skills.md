```yaml
habilidades:
  - nome: cliente_por_nome
    descricao: busca cliente por nome com regex case-insensitive
    entrada:
      nome: string
    saida:
      cliente: object        # ou null se nao encontrado

  - nome: tickets_abertos_do_cliente
    descricao: lista tickets do cliente onde status != "fechado"
    entrada:
      client_id: string
    saida:
      tickets: list

  - nome: erros_do_ticket
    descricao: traz erros correlacionados ao ticket (ticket.erros_correlacionados[])
    entrada:
      ticket: object
    saida:
      erros: list

  - nome: rcas_similares
    descricao: busca RCAs historicos com stacktrace similar — exige client_id ou tipo_erro
    entrada:
      stacktrace: string
      limit: int
      client_id: string
      tipo_erro: string
    saida:
      rcas: list

  - nome: registrar_rca
    descricao: insere RCA em rcas e marca ticket.status=fechado (ACAO SENSIVEL)
    entrada:
      ticket_id: string
      conclusao: string
      evidencias: list
    saida:
      rca_id: string
```
