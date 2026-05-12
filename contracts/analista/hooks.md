```yaml
ganchos:
  antes_da_etapa: log
  apos_etapa: log
  antes_da_acao: log         # registrar_rca merece destaque por ser escrita
  apos_acao: log
  em_erro: alerta            # pymongo.ServerSelectionTimeoutError eh comum se Mongo cai
```
