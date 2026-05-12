```yaml
ferramentas_obrigatorias:
  - cliente_por_nome           # sem cliente, nada mais faz sentido

limites:
  max_etapas: 4                # cliente → tickets → erros → rcas_similares
  limite_tempo_segundos: 10    # queries Mongo locais — se passar disso, algo esta errado
  chamadas_ferramenta:
    cliente_por_nome: 1
    tickets_abertos_do_cliente: 1
    erros_do_ticket: 1
    rcas_similares: 3          # 1 por erro correlacionado (tipicamente 1-3)
    registrar_rca: 1           # so a Triagem chama, no estado PUBLICANDO
    total: 7

acoes_sensiveis:
  - registrar_rca              # INSERT em rcas + UPDATE ticket.status=fechado (irreversivel sem re-seed)

politicas:
  - rcas_similares SEMPRE com client_id ou tipo_erro — sem isso traz ruido cross-cliente (Acme vs Gama)
  - cliente_por_nome usa regex case-insensitive — match parcial intencional ("acme" pega "Acme Corp")
  - $text + textScore com fallback regex (mongomock dos testes nao suporta $text)
  - so chamar registrar_rca quando Critic aprovou (veredito.aprovado=true)
```
