```yaml
habilidades:
  - nome: filesystem.read_text_file
    descricao: le um arquivo de log relativo ao root ./data (ex. logs/acme.log)
    entrada:
      path: string
    saida:
      content: string

  - nome: playwright.browser_navigate
    descricao: navega para URL headless e retorna HTTP status + titulo
    entrada:
      url: string
    saida:
      status: int
      title: string

  - nome: playwright.browser_snapshot
    descricao: captura snapshot DOM acessivel da pagina atual (texto, nao screenshot)
    entrada: {}
    saida:
      snapshot: string

  - nome: github.search_code
    descricao: busca trechos de codigo no repo SENTINEL_GITHUB_REPO (read-only)
    entrada:
      query: string
      repo: string
    saida:
      matches: list
```
