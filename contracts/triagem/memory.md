```yaml
memoria_curta:
  guardar:
    - cliente                 # inv.cliente — usado em conclusao e RCA
    - ticket                  # inv.ticket — fonte de log_path, url, deploy_suspeito
    - evidencias              # inv.evidencias — agregado de todos os sub-agentes
    - confianca               # inv.confianca — recalculada apos cada coleta
    - historico_estados       # snapshot por iteracao
  descartar:
    - prompts_completos       # mensagens system dos sub-agentes (verbosas, repetitivas)
    - tool_calls_raw          # MCPs retornam tool_use blocks gigantes — so guarda o parsed
    - mensagens_intermediarias_llm
  max_registros: 30           # margem para max_iterations=5 * 6 estados

resumo_final:
  max_linhas: 6
  campos:
    - cliente
    - conclusao
    - confianca
    - iteracoes
    - veredito_critic
    - caminho_relatorio
```
