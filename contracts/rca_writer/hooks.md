```yaml
ganchos:
  antes_da_etapa: log
  apos_etapa: log
  antes_da_acao: alerta        # salvar e escrita em disco — vale destacar
  apos_acao: log
  em_erro: alerta              # PermissionError, ENOSPC, encoding — todos importam aqui
```
