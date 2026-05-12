```yaml
habilidades:
  - nome: render_rca
    descricao: monta markdown a partir do template local (cabecalho + conclusao + tabela de evidencias + ressalvas)
    entrada:
      cliente: string
      pergunta: string
      conclusao: string
      evidencias: list
      confianca: float
      iteracao: int
      ressalvas: list
    saida:
      markdown: string

  - nome: salvar
    descricao: escreve markdown em reports/rca_<ticket_id>.md (ACAO SENSIVEL — sobrescreve)
    entrada:
      markdown: string
      ticket_id: string
    saida:
      caminho: string
```
