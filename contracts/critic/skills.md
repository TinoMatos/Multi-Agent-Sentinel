```yaml
habilidades:
  - nome: heuristicas
    descricao: checagens deterministicas (evidencias <2, deploy sem commit, metrica sem grafana)
    entrada:
      conclusao: string
      evidencias: list
    saida:
      motivos: list

  - nome: sanity_llm
    descricao: pergunta a LLM (modelo fast) por contradicoes entre conclusao e evidencias
    entrada:
      conclusao: string
      evidencias: list
    saida:
      contradicoes: list         # maximo 3
```
