# Multi-Agent Technical Sentinel

Sistema multiagente que **investiga incidentes técnicos** correlacionando MongoDB + Grafana + Filesystem + Playwright + GitHub e gera um RCA em markdown. Não é chatbot Q&A — você dá um sintoma com cliente (ex: *"Acme está fora do ar"*) e ele devolve causa + evidências.

**Stack:** Python 3.11+, LangChain + LangGraph, MCPs via `langchain-mcp-adapters`, MongoDB, Streamlit, OpenRouter (LLM).

---

## Pipeline

```
Triagem → [Analista (Mongo) ‖ Observabilidade (Grafana)] → Técnico (Filesystem + Playwright + GitHub) → Critic → RCA
```

State machine com loop: confiança ≥80% confirma; <80% re-delega; max 5 iterações. Critic valida antes de publicar (anti-alucinação).

---

## Instalação

### Pré-requisitos

- **Python** 3.11+
- **Node.js** 18+ (MCPs rodam via `npx`)
- **MongoDB** rodando em `localhost:27017` ([Community Server](https://www.mongodb.com/try/download/community) ou `docker run -d -p 27017:27017 mongo`)
- **mongosh** (pra rodar o seed)
- **Chave OpenRouter** — sem ela o sistema roda em modo degradado determinístico

### Setup (uma vez)

```bash
git clone https://github.com/<seu-user>/multi-agent-sentinel.git && cd multi-agent-sentinel
pip install -r requirements.txt
cp .env.example .env       # edite e ponha OPENROUTER_API_KEY=sk-or-v1-...
mongosh "mongodb://localhost:27017/sentinel" data/seed_mongo.js
npx -y playwright install chromium
```

### Rodar

```bash
python -m streamlit run app.py     # UI em http://localhost:8501 (recomendado)
python -m agents.triagem "Por que o sistema da Acme esta caindo?"   # CLI
python -m pytest -v                # testes (rodam sem API key)
```

> Streamlit não acha `streamlit.exe` no Windows? Use `python -m streamlit`. CLI não carrega `.env` automaticamente — exporte as variáveis antes ou use a UI.

---

## Cenários do seed

| Cliente | Sintoma | Causa esperada |
|---|---|---|
| Acme Corp | Site fora do ar | Deploy ruim — null pointer em `resolveTenant` |
| Beta SaaS | Painel lento (>10s) | Query Mongo sem índice |
| Gama Logística | Pagamentos falhando | Stripe API timeout (dependência externa) |
| Delta Health | Pods reiniciando ~3 dias | Memory leak (heap cresce ~50MB/h) |
| Echo Fintech | Alerta noturno | Falso positivo (rolling restart) — Critic deve vetar |
| Foxtrot Marketplace | Busca/recomendação intermitente | Rate-limit em cascata entre serviços internos |
| Golf Bank | Workers de conciliação parados | Rotação de secret quebrou auth (mudança fora do código) |
| Hotel Streaming | Erro no novo player | Feature flag rampada para 100% (rollout sem deploy) |

A UI tem botão **Auto-demo (8 cenários)** que roda todos em sequência e mostra um placar com 🟢/🟡/🔴 + 🚫 (vetado pelo Critic). Cada item expande pra ver evidências e RCA.

Re-rode o seed após cada investigação — o Sentinel fecha o ticket no Mongo:

```bash
mongosh "mongodb://localhost:27017/sentinel" data/seed_mongo.js
```

---

## Variáveis de ambiente

| Variável | Default / Efeito se ausente |
|---|---|
| `OPENROUTER_API_KEY` | **Obrigatória** pra LLM. Sem ela: modo degradado determinístico. |
| `MONGO_URI` | `mongodb://localhost:27017/sentinel` |
| `SENTINEL_MODEL` | Default: `deepseek/deepseek-chat-v3.1:free` (Triagem + Técnico) |
| `SENTINEL_MODEL_FAST` | Default: `meta-llama/llama-3.3-70b-instruct:free` (Critic) |
| `GRAFANA_URL` + `GRAFANA_API_KEY` | Sem ambas: confiança capada em 70%. |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | PAT clássico, escopo `public_repo` ou `repo` (read). Sem ele: GitHub MCP em modo degradado. |
| `SENTINEL_USE_GITHUB` | `0` (default) — GitHub MCP fica fora do pipeline. Ative com `1` para usar. |
| `SENTINEL_GITHUB_REPO` | Repo onde o agente fará `search_code` (ex: `tinobelmont/multi-agent-sentinel`). Só é usado quando `SENTINEL_USE_GITHUB=1`. |

### Ativando o GitHub MCP

Os SHAs do seed são fictícios — não existem em nenhum repositório real. Por isso o agente é instruído a usar **apenas `search_code`**, nunca `get_commit`/`get_pull_request` em SHAs do stacktrace. Pra ativar:

1. Suba este projeto no seu GitHub.
2. Gere um PAT em [github.com/settings/tokens](https://github.com/settings/tokens) com escopo `public_repo` (ou `repo` se for privado). **Não marque nenhum escopo de escrita.**
3. No `.env`:

   ```bash
   GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
   SENTINEL_USE_GITHUB=1
   SENTINEL_GITHUB_REPO=seu-user/multi-agent-sentinel
   ```

4. Reinicie o Streamlit. O agente passa a buscar nomes de função/arquivo dos stacktraces (`resolveTenant`, `OAuthClient`, etc.) no seu repo e devolve trechos reais como evidência tipo `github` 🐙.

---

## Estrutura

```
agents/         # triagem (orchestrator), analista, tecnico, observabilidade, critic, rca_writer
mcp/config.json # registro dos 5 MCPs (filesystem, mongodb, grafana, playwright, github)
guards/         # output_guard (PII/segredos) + safeguards (max_iterations, token budget)
data/seed_mongo.js  # 8 clientes, 9 tickets, 9 erros, 2 RCAs históricos
config/llm.json # modelos LLM (override via SENTINEL_MODEL*)
app.py          # UI Streamlit
tests/          # pytest, ~30 casos, modo degradado
reports/        # RCAs gerados (.md por ticket)
```

---

## Troubleshooting

| Sintoma | Correção |
|---|---|
| `pymongo.ServerSelectionTimeoutError` | MongoDB não está rodando. |
| Confiança 15%, *"cliente não encontrado"* | Ticket já foi fechado — re-rode o seed. |
| `streamlit: command not found` | Use `python -m streamlit run app.py`. |
| `MCP grafana indisponivel: FileNotFoundError` | OK ignorar — cai em modo degradado. |
| Tudo em 3s + evidências `(degradado)` | `.env` não carregou ou falta `OPENROUTER_API_KEY`. |
| Auto-demo travando em "VALIDANDO" por minutos | GitHub MCP buscando commits fake na API real. Mantenha `SENTINEL_USE_GITHUB=0` quando rodar com o seed. |
| Sidebar mostra `GitHub MCP — sem token` | Cole o PAT em `GITHUB_PERSONAL_ACCESS_TOKEN` no `.env` e reinicie o Streamlit. |
| Sidebar mostra `GitHub MCP — desativado` | Token configurado mas `SENTINEL_USE_GITHUB=0`. Ative com `1` se apontar pra repo real. |
