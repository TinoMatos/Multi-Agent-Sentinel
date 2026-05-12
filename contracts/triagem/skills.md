```yaml
habilidades:
  - nome: call_analista
    descricao: delega para o Analista coletar contexto Mongo (cliente, ticket, erros, RCAs historicos)
    entrada:
      pergunta: string
    saida:
      evidencias: list

  - nome: call_observabilidade
    descricao: delega para Observabilidade coletar alertas Grafana ao vivo (em paralelo com Analista)
    entrada:
      pergunta: string
    saida:
      evidencias: list

  - nome: call_tecnico
    descricao: delega para o Tecnico confirmar a hipotese via filesystem + playwright + github
    entrada:
      hipotese: string
    saida:
      evidencias: list

  - nome: call_critic
    descricao: valida se as evidencias sustentam a conclusao antes de publicar
    entrada:
      conclusao: string
      evidencias: list
    saida:
      aprovado: bool
      confianca: float
      motivos: list

  - nome: call_backlog_decomposer
    descricao: apos RCA aprovado, decompoe a conclusao em backlog de fix (epicos+stories+riscos+perguntas)
    entrada:
      objetivo: string
    saida:
      caminho_arquivo: string

  - nome: call_rca_writer
    descricao: renderiza o markdown final do RCA e salva em reports/
    entrada:
      cliente: string
      pergunta: string
      conclusao: string
      evidencias: list
      confianca: float
      iteracao: int
      ressalvas: list
    saida:
      caminho: string
```
