"""Streamlit UI do Multi-Agent Sentinel.

Roda: streamlit run app.py
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import time

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

from agents import triagem, observabilidade  # noqa: E402
from agents._llm import disponivel as llm_disponivel  # noqa: E402

st.set_page_config(
    page_title="Multi-Agent Sentinel",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- estilo ----------
st.markdown(
    """
<style>
/* esconder elementos default do streamlit */
#MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden;}
.stDeployButton {display:none !important;}

/* fundo com gradiente sutil */
.stApp {
    background: radial-gradient(ellipse at top left, #0f172a 0%, #0a0e1a 50%, #050810 100%);
}

/* HERO header animado */
.hero {
    padding: 1.5rem 0 0.5rem 0;
    margin-bottom: 0.5rem;
}
.hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 35%, #ec4899 70%, #f59e0b 100%);
    background-size: 300% 300%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shimmer 6s ease-in-out infinite;
    letter-spacing: -0.02em;
    margin: 0;
}
@keyframes shimmer {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}
.hero-sub {
    color: #94a3b8;
    font-size: 0.95rem;
    margin-top: 0.3rem;
}
.hero-badge {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    background: rgba(99,102,241,0.15);
    border: 1px solid rgba(99,102,241,0.4);
    color: #a5b4fc;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-right: 0.4rem;
}

/* métricas custom (cards glass) */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.8rem;
    margin: 1rem 0 1.2rem 0;
}
.metric-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.6) 0%, rgba(15,23,42,0.4) 100%);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 1rem 1.2rem;
    border-radius: 14px;
    border: 1px solid rgba(99,102,241,0.15);
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
    border-color: rgba(99,102,241,0.4);
}
.metric-label {
    color: #94a3b8;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f1f5f9;
    margin-top: 0.2rem;
    line-height: 1.1;
}
.metric-value.green { color: #10b981; }
.metric-value.yellow { color: #f59e0b; }
.metric-value.red { color: #ef4444; }
.metric-value.blue { color: #6366f1; }

/* barra de confiança */
.confidence-bar {
    height: 4px;
    border-radius: 2px;
    background: #1e293b;
    margin-top: 0.5rem;
    overflow: hidden;
}
.confidence-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

/* pills de estado com conector */
.pills-wrap {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 0.8rem 0;
    flex-wrap: wrap;
}
.state-pill {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.85rem;
    border-radius: 999px;
    background: rgba(30,41,59,0.6);
    color: #64748b;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border: 1px solid rgba(71,85,105,0.3);
    transition: all 0.3s ease;
}
.state-pill.active {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border-color: transparent;
    box-shadow: 0 0 20px rgba(99,102,241,0.5);
    animation: pulse 1.5s ease-in-out infinite;
}
.state-pill.done {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    border-color: transparent;
}
.state-pill.completed {
    background: rgba(16,185,129,0.15);
    color: #34d399;
    border-color: rgba(16,185,129,0.3);
}
@keyframes pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(99,102,241,0.5); }
    50% { box-shadow: 0 0 30px rgba(99,102,241,0.8); }
}
.pill-arrow {
    color: #475569;
    margin: 0 0.3rem;
    font-size: 0.8rem;
}

/* banner de causa raiz */
.causa-banner {
    background: linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(99,102,241,0.1) 100%);
    border: 1px solid rgba(16,185,129,0.4);
    border-left: 4px solid #10b981;
    padding: 1rem 1.2rem;
    border-radius: 10px;
    margin: 1rem 0;
}
.causa-banner.warn {
    background: linear-gradient(135deg, rgba(245,158,11,0.15) 0%, rgba(99,102,241,0.1) 100%);
    border-color: rgba(245,158,11,0.4);
    border-left-color: #f59e0b;
}
.causa-label {
    color: #10b981;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.3rem;
}
.causa-banner.warn .causa-label { color: #f59e0b; }
.causa-text {
    color: #f1f5f9;
    font-size: 1.05rem;
    font-weight: 500;
    line-height: 1.5;
}

/* cards de evidência */
.evidencia {
    background: rgba(15,23,42,0.5);
    backdrop-filter: blur(8px);
    padding: 0.7rem 1rem;
    border-left: 3px solid #6366f1;
    border-radius: 6px;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
    transition: transform 0.15s ease, background 0.15s ease;
    animation: slideIn 0.4s ease-out;
}
.evidencia:hover {
    transform: translateX(3px);
    background: rgba(15,23,42,0.8);
}
@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}
.tipo-mongo{border-left-color:#10b981}
.tipo-erro{border-left-color:#ef4444}
.tipo-grafana{border-left-color:#f59e0b}
.tipo-rca_historico{border-left-color:#8b5cf6}
.tipo-commit,.tipo-github_pr,.tipo-github_issue{border-left-color:#6b7280}
.tipo-playwright{border-left-color:#06b6d4}
.tipo-filesystem{border-left-color:#84cc16}

.ev-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
}
.ev-icon {
    font-size: 0.9rem;
}
.ev-tipo {
    font-weight: 700;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    color: #cbd5e1;
}
.ev-ref {
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 0.7rem;
    color: #64748b;
    background: rgba(0,0,0,0.3);
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
}
.ev-nota {
    color: #cbd5e1;
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 0.8rem;
    line-height: 1.5;
    word-break: break-word;
}

/* status sidebar */
.status-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.6rem;
    background: rgba(15,23,42,0.5);
    border-radius: 6px;
    margin-bottom: 0.3rem;
    font-size: 0.85rem;
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.status-dot.ok { background: #10b981; box-shadow: 0 0 8px #10b981; }
.status-dot.degraded { background: #f59e0b; box-shadow: 0 0 8px #f59e0b; }
.status-dot.off { background: #ef4444; }

/* secao headers */
.section-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #f1f5f9;
    margin: 0.5rem 0 0.8rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* botão investigar custom */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.4) !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(99,102,241,0.6) !important;
}

/* ajustes finos sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0e1a 0%, #070a14 100%);
    border-right: 1px solid rgba(99,102,241,0.1);
    min-width: 320px !important;
    width: 320px !important;
    transform: translateX(0) !important;
    visibility: visible !important;
}
section[data-testid="stSidebar"][aria-expanded="false"] {
    margin-left: 0 !important;
}
/* esconde o botao colapsar (evita o bug de toggle automatico) */
button[data-testid="stSidebarCollapseButton"],
button[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: none !important;
}
/* garante que o conteudo principal nao fique por baixo da sidebar */
section.main, [data-testid="stAppViewContainer"] > .main {
    margin-left: 320px !important;
}

/* RCA box */
.rca-box {
    background: rgba(15,23,42,0.4);
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 12px;
    padding: 1.2rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- ícones por tipo ----------
ICON_TIPO = {
    "mongo": "🗄️",
    "erro": "💥",
    "grafana": "📈",
    "rca_historico": "📚",
    "commit": "🔧",
    "github_pr": "🔀",
    "github_issue": "🐛",
    "playwright": "🌐",
    "filesystem": "📁",
    "github": "🐙",
}

# ---------- sidebar ----------
with st.sidebar:
    st.markdown("# 🛰️ Sentinel")
    st.caption("Multi-Agent Technical Sentinel")
    st.divider()

    st.markdown("##### Status dos componentes")

    @st.cache_data(ttl=30)
    def _check_status():
        status = {}
        status["OpenRouter"] = ("ok", "online") if llm_disponivel() else ("off", "degradado")
        status["Grafana MCP"] = ("ok", "online") if observabilidade.disponivel() else ("degraded", "degradado")
        # MongoDB — conexão direta
        try:
            import pymongo  # type: ignore
            uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/sentinel")
            pymongo.MongoClient(uri, serverSelectionTimeoutMS=500).admin.command("ping")
            status["MongoDB"] = ("ok", "online")
        except Exception:
            status["MongoDB"] = ("off", "offline")
        # binários necessários para os MCPs via npx
        npx = shutil.which("npx") is not None
        status["Filesystem MCP"] = ("ok", "pronto") if npx else ("off", "npx ausente")
        status["Playwright MCP"] = ("ok", "pronto") if npx else ("off", "npx ausente")
        if not npx:
            status["GitHub MCP"] = ("off", "npx ausente")
        elif not os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"):
            status["GitHub MCP"] = ("degraded", "sem token")
        elif os.getenv("SENTINEL_USE_GITHUB") != "1":
            status["GitHub MCP"] = ("degraded", "desativado")
        elif not os.getenv("SENTINEL_GITHUB_REPO", "").strip():
            status["GitHub MCP"] = ("degraded", "sem repo")
        else:
            status["GitHub MCP"] = ("ok", "ativo")
        return status

    for nome, (estado, label_st) in _check_status().items():
        st.markdown(
            f'<div class="status-item"><span class="status-dot {estado}"></span>'
            f'{nome}<span style="margin-left:auto;color:#64748b;font-size:0.72rem;">{label_st}</span></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("##### Cenários do seed")
    cenarios = {
        "✏️ Custom (sua pergunta)": None,
        "Acme Corp — Indisponibilidade no login": "Por que o sistema da Acme esta caindo?",
        "Beta SaaS — Degradação no painel admin": "Por que o painel administrativo da Beta SaaS esta lento?",
        "Gama Logística — Falha no checkout": "Por que os pagamentos da Gama Logistica estao falhando?",
        "Delta Health — Reinícios recorrentes da API": "Por que os pods da API Delta Health estao sendo reiniciados periodicamente?",
        "Echo Fintech — Alerta noturno sob investigação": "Por que o sistema da Echo Fintech disparou alertas de madrugada?",
        "Foxtrot Marketplace — Falhas em cascata na busca": "Por que a busca e as recomendacoes do marketplace Foxtrot estao falhando intermitentemente?",
        "Golf Bank — Workers de conciliação parados": "Por que os workers de conciliacao do Golf Bank pararam de processar desde a madrugada?",
        "Hotel Streaming — Erro no novo player": "Por que o novo player da Hotel Streaming esta dando erro para usuarios desde a manha?",
    }
    label = st.radio(
        "Selecione um caso:",
        list(cenarios.keys()),
        index=0,
        label_visibility="collapsed",
        help=(
            "Cada cenario exercita um padrao diferente:\n"
            "• Acme: deploy ruim + RCA historico (regressao)\n"
            "• Beta: query Mongo lenta sem deploy (indice ausente)\n"
            "• Gama: dependencia externa (Stripe timeout)\n"
            "• Delta: regressao silenciosa (memory leak ha 3 dias)\n"
            "• Echo: falso positivo (deploy era hotfix) — Critic deve vetar\n"
            "• Foxtrot: rate-limit em cascata entre servicos internos\n"
            "• Golf: rotacao de secret quebrou auth (mudanca fora do codigo)\n"
            "• Hotel: feature flag rampada para 100% (rollout sem deploy)"
        ),
    )
    cenario = cenarios[label]
    pergunta = (
        st.text_input("Pergunta custom:", value="")
        if cenario is None
        else cenario
    )
    # --- Clarificação inline: se pergunta custom não identifica cliente, perguntar aqui mesmo ---
    if cenario is None and pergunta:
        from agents.triagem import _extrair_nome_cliente as _ext
        if not _ext(pergunta):
            from agents import analista as _an
            try:
                _nomes = [c["nome"] for c in _an._db().clientes.find({}, {"nome": 1})]
            except Exception:
                _nomes = []
            if _nomes:
                st.caption("🤝 Cliente não identificado — selecione:")
                _sel = st.selectbox(
                    "Cliente:",
                    options=[None] + _nomes,
                    index=0,
                    format_func=lambda x: "— escolha um cliente —" if x is None else x,
                    key="sidebar_cliente_sel",
                    label_visibility="collapsed",
                )
                if _sel:
                    pergunta = f"{pergunta} (cliente: {_sel})"
    auto_reset = st.checkbox(
        "🔄 Auto-reset (reabre ticket antes)",
        value=True,
        help="Reabre tickets fechados por investigações anteriores. Sem isso você vê 'cliente sem tickets' depois da 1ª rodada.",
    )
    st.session_state["auto_reset_flag"] = auto_reset
    # Modo interativo sempre ligado — agente pergunta cliente e avisa quando pergunta nao bate com ticket
    st.session_state["modo_interativo"] = True
    rodar = st.button("▶️  INVESTIGAR", type="primary", use_container_width=True)
    auto_demo = st.button("🚀  AUTO-DEMO (8 cenários)", use_container_width=True)

    st.divider()
    st.caption("**Pipeline**")
    st.caption("Triagem → [Analista ‖ Obs.] → Técnico → Critic → RCA")

    # ---------- histórico ----------
    if "historico" not in st.session_state:
        st.session_state.historico = []
    if st.session_state.historico:
        st.divider()
        st.markdown("##### 📜 Investigações recentes")
        for i, h in enumerate(reversed(st.session_state.historico[-5:])):
            cor = "#10b981" if h["confianca"] >= 0.8 else ("#f59e0b" if h["confianca"] >= 0.5 else "#ef4444")
            st.markdown(
                f'<div class="status-item" style="font-size:0.78rem;">'
                f'<span class="status-dot" style="background:{cor};"></span>'
                f'{h["cliente"][:18]}'
                f'<span style="margin-left:auto;color:#64748b;">{h["confianca"]:.0%} · {h["elapsed"]:.0f}s</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ---------- header ----------
st.markdown(
    """
<div class="hero">
    <div>
        <span class="hero-badge">🛰️ Multi-Agent</span>
        <span class="hero-badge" style="background:rgba(16,185,129,0.15);border-color:rgba(16,185,129,0.4);color:#34d399;">
            Autonomous SRE
        </span>
    </div>
    <h1 class="hero-title">Multi-Agent Technical Sentinel</h1>
    <p class="hero-sub">Investigação autônoma de incidentes — correlaciona MongoDB · Grafana · Filesystem · Playwright em segundos.</p>
</div>
""",
    unsafe_allow_html=True,
)

estados_pills = ["HIPOTESE", "COLETANDO", "CONFIRMANDO", "VALIDANDO", "PUBLICANDO", "DONE"]


def render_pills(estado_atual: str):
    if not estado_atual:
        idx_atual = -1
    else:
        try:
            idx_atual = estados_pills.index(estado_atual)
        except ValueError:
            idx_atual = -1

    parts = ['<div class="pills-wrap">']
    for i, s in enumerate(estados_pills):
        cls = "state-pill"
        if i < idx_atual:
            cls += " completed"
        elif i == idx_atual:
            cls += " done" if s == "DONE" else " active"
        parts.append(f'<span class="{cls}">{s}</span>')
        if i < len(estados_pills) - 1:
            parts.append('<span class="pill-arrow">→</span>')
    parts.append("</div>")
    return "".join(parts)


# ---------- container principal ----------
status_container = st.empty()
banner_container = st.empty()
metrics_container = st.empty()
col_ev, col_rca = st.columns([1, 1])
ev_container = col_ev.empty()
rca_container = col_rca.empty()


def cor_confianca(c: float) -> str:
    if c >= 0.8:
        return "green"
    if c >= 0.5:
        return "yellow"
    if c > 0:
        return "red"
    return "blue"


def fill_color(c: float) -> str:
    if c >= 0.8:
        return "linear-gradient(90deg,#10b981,#34d399)"
    if c >= 0.5:
        return "linear-gradient(90deg,#f59e0b,#fbbf24)"
    if c > 0:
        return "linear-gradient(90deg,#ef4444,#f87171)"
    return "linear-gradient(90deg,#6366f1,#8b5cf6)"


def render_metricas(inv):
    with metrics_container.container():
        cliente = inv.cliente["nome"] if inv.cliente else "—"
        c = inv.confianca or 0.0
        cor = cor_confianca(c)
        n_ev = len(inv.evidencias)
        ev_cor = "green" if n_ev >= 5 else ("yellow" if n_ev >= 1 else "blue")
        st.markdown(
            f"""
<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-label">🏢 Cliente</div>
        <div class="metric-value blue" style="font-size:1.4rem;">{cliente}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">🔄 Iterações</div>
        <div class="metric-value">{inv.iteracao}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">🎯 Confiança</div>
        <div class="metric-value {cor}">{c:.0%}</div>
        <div class="confidence-bar"><div class="confidence-fill" style="width:{c*100:.0f}%;background:{fill_color(c)};"></div></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">📋 Evidências</div>
        <div class="metric-value {ev_cor}">{n_ev}</div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )


def extrair_causa(inv) -> str | None:
    """Tenta achar a frase de causa raiz no relatório ou nas evidências."""
    if inv.relatorio:
        m = re.search(r"(?im)^#+\s*conclus[aã]o\s*\n+(.+?)(?:\n#|\n\n|\Z)", inv.relatorio, re.S)
        if m:
            txt = m.group(1).strip()
            if txt and "andamento" not in txt.lower() and "desconhecido" not in txt.lower():
                return txt[:300]
    for e in inv.evidencias:
        if e.get("tipo") == "rca_historico" and e.get("nota"):
            return e["nota"][:300]
    return None


def render_banner(inv):
    causa = extrair_causa(inv)
    c = inv.confianca or 0.0
    with banner_container.container():
        # Aviso de desalinhamento (pergunta nao bate com ticket encontrado)
        if getattr(inv, "motivo_desalinhamento", None):
            st.warning(f"🔀 **Alinhamento baixo** ({inv.alinhamento:.0%}): {inv.motivo_desalinhamento}")
        if causa and c >= 0.7:
            st.markdown(
                f"""
<div class="causa-banner">
    <div class="causa-label">🎯 Causa raiz identificada</div>
    <div class="causa-text">{causa}</div>
</div>
""",
                unsafe_allow_html=True,
            )
        elif c > 0 and c < 0.5:
            st.markdown(
                """
<div class="causa-banner warn">
    <div class="causa-label">⚠️ Investigação inconclusiva</div>
    <div class="causa-text">Confiança baixa — Critic vetou conclusão automática. Revise as evidências abaixo.</div>
</div>
""",
                unsafe_allow_html=True,
            )


def render_evidencias(inv):
    with ev_container.container():
        st.markdown('<div class="section-title">📊 Evidências coletadas</div>', unsafe_allow_html=True)
        if not inv.evidencias:
            st.info("Aguardando coleta...")
            return
        for e in inv.evidencias:
            tipo = e["tipo"]
            icon = ICON_TIPO.get(tipo, "📌")
            st.markdown(
                f"""<div class="evidencia tipo-{tipo}">
<div class="ev-header">
    <span class="ev-icon">{icon}</span>
    <span class="ev-tipo">{tipo}</span>
    <span class="ev-ref">{e["ref"]}</span>
</div>
<div class="ev-nota">{e["nota"]}</div>
</div>""",
                unsafe_allow_html=True,
            )


def render_rca(inv):
    with rca_container.container():
        st.markdown('<div class="section-title">📄 RCA gerado</div>', unsafe_allow_html=True)
        if inv.relatorio:
            with st.container():
                st.markdown(f'<div class="rca-box">', unsafe_allow_html=True)
                st.markdown(inv.relatorio)
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("RCA será gerado ao final da investigação.")


def render_diff_rca(inv):
    """Mostra diff entre o incidente atual e o RCA histórico mais similar."""
    historicos = [e for e in inv.evidencias if e.get("tipo") == "rca_historico"]
    if not historicos or not inv.ticket:
        return
    h = historicos[0]
    atual = inv.ticket.get("descricao", "")
    passado = h.get("nota", "")
    with st.expander("🔁 Comparar com incidente histórico similar", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🆕 Incidente atual**")
            st.info(atual)
        with c2:
            st.markdown(f"**📚 Histórico (`{h.get('ref', '?')[:12]}`)**")
            st.info(passado)
        st.caption("→ Sugere regressão se a conclusão histórica também menciona o mesmo deploy/causa.")


def render_telemetria(inv, elapsed: float):
    t = inv.telemetria
    if t.total_tokens == 0:
        return
    custo = t.custo_usd
    custo_str = f"${custo:.4f}" if custo is not None else "—"
    with st.expander(f"📊 Telemetria · {t.total_tokens} tokens · {custo_str}", expanded=False):
        st.json(t.resumo())


def render_replay(inv):
    if not inv.historico_estados or len(inv.historico_estados) < 2:
        return
    with st.expander("⏯️ Replay da state machine", expanded=False):
        idx = st.slider(
            "Passo da investigação",
            min_value=0,
            max_value=len(inv.historico_estados) - 1,
            value=len(inv.historico_estados) - 1,
            key=f"replay_{id(inv)}",
        )
        snap = inv.historico_estados[idx]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Estado", snap["estado"].upper())
        c2.metric("Iteração", snap["iteracao"])
        c3.metric("Evidências", snap["evidencias"])
        c4.metric("Tempo", f"{snap['elapsed_s']:.1f}s")
        st.progress(min(snap["confianca"], 1.0), text=f"Confiança {snap['confianca']:.0%}")


# ---------- execucao ----------

def _executar(pergunta_q: str, mostrar_pills: bool = True):
    from agents.triagem import Investigacao

    # Clarificação de cliente eh feita na sidebar (antes do INVESTIGAR) — aqui so executa.
    if st.session_state.get("auto_reset_flag", True):
        try:
            from agents.seed_helper import reset_tickets
            reset_tickets()
        except Exception:
            pass  # mongo offline / sem permissao — segue mesmo assim

    inv_shared = Investigacao(pergunta=pergunta_q)

    async def run_with_progress():
        task = asyncio.create_task(triagem.run(pergunta_q, inv=inv_shared))
        ultimo = None
        while not task.done():
            if mostrar_pills:
                atual = inv_shared.estado.value.upper()
                if atual != ultimo:
                    status_container.markdown(render_pills(atual), unsafe_allow_html=True)
                    ultimo = atual
            await asyncio.sleep(0.15)
        result = await task
        if mostrar_pills:
            status_container.markdown(render_pills("DONE"), unsafe_allow_html=True)
        return result

    t0 = time.time()
    try:
        inv_local = asyncio.run(run_with_progress())
    except Exception as e:
        st.error(f"Erro: {e}")
        st.stop()
    elapsed = time.time() - t0

    # registra no histórico
    st.session_state.historico.append({
        "cliente": inv_local.cliente["nome"] if inv_local.cliente else "?",
        "pergunta": pergunta_q,
        "confianca": inv_local.confianca,
        "elapsed": elapsed,
        "n_evidencias": len(inv_local.evidencias),
    })
    return inv_local, elapsed


def _render_resultado(inv_r, elapsed: float):
    with status_container.container():
        st.markdown(render_pills("DONE"), unsafe_allow_html=True)
        st.success(
            f"✅ Investigação concluída em **{elapsed:.1f}s** · "
            f"{len(inv_r.evidencias)} evidências · confiança {inv_r.confianca:.0%}"
        )
    render_banner(inv_r)
    render_metricas(inv_r)
    render_evidencias(inv_r)
    render_rca(inv_r)
    render_diff_rca(inv_r)
    render_replay(inv_r)
    render_telemetria(inv_r, elapsed)

    # botão de re-investigar com escopo
    st.divider()
    with st.expander("🔍 Re-investigar com escopo refinado", expanded=False):
        escopo = st.text_input(
            "Adicione um filtro à investigação original:",
            placeholder="ex: ignore o deploy X / olhe só nas últimas 2h / foque no checkout",
            key=f"escopo_{id(inv_r)}",
        )
        if st.button("🔄 Re-investigar", key=f"reinv_{id(inv_r)}"):
            nova_pergunta = f"{inv_r.pergunta} ({escopo})" if escopo else inv_r.pergunta
            st.session_state["_reinvestigar"] = nova_pergunta
            st.rerun()

    if inv_r.rca_id:
        st.toast(f"📝 RCA salvo no MongoDB (id={inv_r.rca_id})", icon="✅")
    elif inv_r.ticket:
        st.toast("⚠️ Critic vetou o registro automático — revisar ressalvas", icon="⚠️")


# trigger via botão "Re-investigar" da rodada anterior
pergunta_pendente = st.session_state.pop("_reinvestigar", None)

if auto_demo:
    status_container.empty()
    st.markdown('<div class="section-title">🚀 Auto-demo dos 8 cenários</div>', unsafe_allow_html=True)
    progresso = st.progress(0.0)
    placar = st.empty()
    resultados = []
    labels_por_pergunta = {v: k for k, v in cenarios.items() if v}
    todos_cenarios = [v for v in cenarios.values() if v]
    for i, p in enumerate(todos_cenarios):
        rotulo = labels_por_pergunta.get(p, p)[:70]
        progresso.progress(
            (i + 0.5) / len(todos_cenarios),
            text=f"[{i + 1}/{len(todos_cenarios)}] {rotulo}",
        )
        inv_d, t_d = _executar(p, mostrar_pills=False)
        resultados.append({
            "cliente": inv_d.cliente["nome"] if inv_d.cliente else "?",
            "confianca": inv_d.confianca,
            "tempo": t_d,
            "evidencias": len(inv_d.evidencias),
            "aprovado": getattr(inv_d, "_veredito", None) and inv_d._veredito.aprovado,
            "inv": inv_d,
            "pergunta": p,
        })
    progresso.progress(1.0, text="Concluído")
    placar.markdown("### 📊 Placar")
    st.caption(
        "🟢 alta confiança (≥80%)  ·  "
        "🟡 confiança média (50–79%)  ·  "
        "🔴 baixa confiança (<50%)  ·  "
        "🚫 vetado pelo Critic"
    )
    for idx, r in enumerate(resultados):
        cor = "#10b981" if r["confianca"] >= 0.8 else ("#f59e0b" if r["confianca"] >= 0.5 else "#ef4444")
        if r["confianca"] >= 0.8:
            bolinha = "🟢"
        elif r["confianca"] >= 0.5:
            bolinha = "🟡"
        else:
            bolinha = "🔴"
        if not r["aprovado"]:
            bolinha = f"{bolinha} 🚫"
        titulo = (
            f'{bolinha} {r["cliente"]} — confiança {r["confianca"]:.0%} · '
            f'{r["evidencias"]} evidências · {r["tempo"]:.1f}s'
        )
        with st.expander(titulo, expanded=False):
            st.markdown(
                f'<div style="border-left:3px solid {cor};padding-left:0.6rem;'
                f'color:#94a3b8;font-size:0.8rem;margin-bottom:0.6rem;">{r["pergunta"]}</div>',
                unsafe_allow_html=True,
            )
            inv_e = r["inv"]
            if not inv_e.evidencias:
                st.info("Sem evidências coletadas.")
            else:
                for e in inv_e.evidencias:
                    tipo = e["tipo"]
                    icon = ICON_TIPO.get(tipo, "📌")
                    st.markdown(
                        f"""<div class="evidencia tipo-{tipo}">
<div class="ev-header">
    <span class="ev-icon">{icon}</span>
    <span class="ev-tipo">{tipo}</span>
    <span class="ev-ref">{e["ref"]}</span>
</div>
<div class="ev-nota">{e["nota"]}</div>
</div>""",
                        unsafe_allow_html=True,
                    )
            if inv_e.relatorio:
                st.markdown("**📄 RCA**")
                st.markdown(f'<div class="rca-box">', unsafe_allow_html=True)
                st.markdown(inv_e.relatorio)
                st.markdown('</div>', unsafe_allow_html=True)
    media_conf = sum(r["confianca"] for r in resultados) / max(len(resultados), 1)
    media_t = sum(r["tempo"] for r in resultados) / max(len(resultados), 1)
    st.success(f"🎯 Média: confiança {media_conf:.0%} · tempo {media_t:.1f}s por cenário")

if not auto_demo and ((rodar and pergunta) or pergunta_pendente):
    pergunta_q = pergunta_pendente or pergunta
    inv, elapsed = _executar(pergunta_q)
    _render_resultado(inv, elapsed)
elif not auto_demo:
    with status_container.container():
        st.markdown(render_pills(""), unsafe_allow_html=True)
    st.info("👈 Selecione um cenário e clique em **Investigar** — ou rode o **Auto-demo** pra ver os 8 casos em sequência.")
