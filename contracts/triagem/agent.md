```yaml
nome: triagem
descricao: orquestrador do pipeline de investigacao de incidentes; delega para Analista, Observabilidade, Tecnico e Critic ate fechar um RCA
tipo: task_based         # task_based por default; vira interactive quando run(perguntar=...) eh passado
# modo interactive (CLI: --interactive ou -i): pergunta ao humano quando cliente nao identificado
# e pede confirmacao antes de gravar RCA (registrar_rca eh acao sensivel)

objetivo: produzir_rca_com_evidencias_validadas

contrato_saida:
  formato: relatorio
  campos_obrigatorios:
    - cliente
    - pergunta
    - conclusao
    - evidencias
    - confianca
    - iteracao
    - veredito_critic
  exemplo:
    cliente: "Acme Corp"
    pergunta: "Por que o sistema da Acme esta caindo?"
    conclusao: "Incidente correlacionado ao deploy `abc123`. Recomenda-se rollback."
    evidencias:
      - { tipo: mongo, ref: "ticket-id", nota: "ticket aberto" }
      - { tipo: playwright, ref: "https://acme.example", nota: "HTTP 500 confirmado" }
    confianca: 0.85
    iteracao: 1
    veredito_critic: aprovado
```

Estados (state machine em `agents/triagem.py:22`):
`HIPOTESE → COLETANDO → CONFIRMANDO → VALIDANDO → PUBLICANDO → DONE`
