"""Sentinel Impact Eval — mede qualidade do RCA contra dataset de cenarios.

Inspirado em aula15/memory_eval.py. Cada caso roda em DOIS modos:
  1. com_memoria: execucao normal
  2. sem_memoria: SENTINEL_MEMORY_DISABLED=1 (no-op enquanto memoria nao for plugada;
     hook reservado pra quando memory_adapter entrar no projeto)

6 metricas agregadas, com PASS/FAIL contra thresholds da suite, e relatorio markdown
em reports/evals/sentinel_impact_report_<ts>.md.

Uso (da raiz do projeto):
  python -m evals.eval_runner --suite evals/suites/sentinel_impact_eval.yaml
  python -m evals.eval_runner --suite evals/suites/sentinel_impact_eval.yaml --max-casos 3
  python -m evals.eval_runner --suite evals/suites/sentinel_impact_eval.yaml --skip-sem-memoria

Pre-requisito: MongoDB rodando + seed aplicado (data/seed_mongo.js).
A cada caso o eval chama seed_helper.reset_tickets() pra reabrir os tickets fechados.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

import yaml

from agents import triagem
from agents.seed_helper import reset_tickets


ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------

def _carregar_suite(caminho_suite: Path) -> dict:
    return yaml.safe_load(caminho_suite.read_text(encoding="utf-8"))


def _carregar_dataset(caminho_suite: Path, suite: dict) -> list:
    nome = suite["dataset"]
    candidato = caminho_suite.parent.parent / "datasets" / nome
    if not candidato.exists():
        candidato = caminho_suite.parent / nome
    return json.loads(candidato.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Metricas por caso
# ---------------------------------------------------------------------------

def _contem(texto: str, termos: list) -> list:
    t = (texto or "").lower()
    return [k for k in termos if k.lower() in t]


def _rca_correctness(relatorio: str, expected: list) -> float:
    if not expected:
        return 1.0
    return len(_contem(relatorio, expected)) / len(expected)


def _forbidden_avoidance(relatorio: str, forbidden: list) -> float:
    if not forbidden:
        return 1.0
    vazados = len(_contem(relatorio, forbidden))
    return 1.0 - (vazados / len(forbidden))


def _evidence_coverage(evidencias: list, esperadas: list) -> float:
    if not esperadas:
        return 1.0
    tipos = {e.get("tipo") for e in evidencias}
    presentes = sum(1 for t in esperadas if t in tipos)
    return presentes / len(esperadas)


def _critic_alignment(veredito, esperado_aprovado: bool) -> float:
    if veredito is None:
        return 0.0
    return 1.0 if veredito.aprovado == esperado_aprovado else 0.0


def _degraded_ratio(evidencias: list) -> float:
    if not evidencias:
        return 0.0
    degradadas = sum(
        1 for e in evidencias if "degradado" in (e.get("nota") or "").lower()
    )
    return degradadas / len(evidencias)


def _achatar_recuperados(ctx: dict) -> list:
    itens = []
    for f in ctx.get("fatos", []) or []:
        itens.append(str(f))
    for ep in ctx.get("episodios", []) or []:
        if isinstance(ep, dict):
            itens.append(str(ep.get("resumo") or ep.get("descricao") or ep))
        else:
            itens.append(str(ep))
    for lic in ctx.get("licoes", []) or []:
        if isinstance(lic, dict):
            itens.append(str(lic.get("licao") or lic))
        else:
            itens.append(str(lic))
    return [i for i in itens if i]


def _esperados_unificados(caso: dict) -> list:
    esp = caso.get("contexto_memoria_esperado", {}) or {}
    out = []
    out.extend(esp.get("fatos", []) or [])
    out.extend(esp.get("episodios", []) or [])
    out.extend(esp.get("licoes", []) or [])
    return [str(e) for e in out if e]


def _calc_precision(recuperados: list, esperados: list) -> float:
    if not recuperados:
        return 1.0 if not esperados else 0.0
    if not esperados:
        return 0.0
    relevantes = 0
    for r in recuperados:
        rl = r.lower()
        for e in esperados:
            toks = [t for t in e.lower().split() if len(t) > 3][:3]
            if toks and any(t in rl for t in toks):
                relevantes += 1
                break
    return relevantes / len(recuperados)


def _calc_recall(recuperados: list, esperados: list) -> float:
    if not esperados:
        return 1.0
    if not recuperados:
        return 0.0
    rl = [r.lower() for r in recuperados]
    encontrados = 0
    for e in esperados:
        toks = [t for t in e.lower().split() if len(t) > 3][:3]
        if toks and any(any(t in r for t in toks) for r in rl):
            encontrados += 1
    return encontrados / len(esperados)


def _memory_improvement(iter_sem: int, redel_sem: int, iter_com: int, redel_com: int) -> float:
    """Reducao combinada de iteracoes + redelegacoes. 0 quando memoria nao esta plugada."""
    custo_sem = iter_sem + redel_sem * 2
    custo_com = iter_com + redel_com * 2
    if custo_sem == 0:
        return 0.0
    return (custo_sem - custo_com) / custo_sem


# ---------------------------------------------------------------------------
# Execucao de caso
# ---------------------------------------------------------------------------

async def _rodar_caso(pergunta: str, sem_memoria: bool):
    """Reseta tickets e roda triagem.run. Retorna (Investigacao, veredito)."""
    reset_tickets()
    if sem_memoria:
        os.environ["SENTINEL_MEMORY_DISABLED"] = "1"
    else:
        os.environ.pop("SENTINEL_MEMORY_DISABLED", None)
    try:
        inv = await triagem.run(pergunta)
    finally:
        os.environ.pop("SENTINEL_MEMORY_DISABLED", None)
    veredito = getattr(inv, "_veredito", None)
    return inv, veredito


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def executar_eval(caminho_suite: Path, max_casos: int | None, skip_sem_memoria: bool) -> dict:
    suite = _carregar_suite(caminho_suite)
    dataset = _carregar_dataset(caminho_suite, suite)
    if max_casos is not None:
        dataset = dataset[:max_casos]

    thresholds = suite.get("thresholds", {})

    print(f"\n{'=' * 60}")
    print(f"  SENTINEL IMPACT EVAL")
    print(f"  Dataset: {len(dataset)} casos")
    print(f"  Modo: {'com memoria apenas' if skip_sem_memoria else 'com vs sem memoria (2 execucoes/caso)'}")
    print(f"{'=' * 60}\n")

    inicio = time.time()
    resultados = []

    for i, caso in enumerate(dataset, 1):
        cid = caso.get("id", f"caso_{i}")
        print(f"\n--- CASO {i}/{len(dataset)}: {cid} ---")
        print(f"Pergunta: {caso['pergunta']}")

        # baseline: sem memoria
        if skip_sem_memoria:
            iter_sem = redel_sem = 0
        else:
            print(">>> SEM memoria...")
            inv_sem, _ = await _rodar_caso(caso["pergunta"], sem_memoria=True)
            iter_sem = inv_sem.iteracao
            redel_sem = inv_sem.redelegacoes

        # com memoria
        print(">>> COM memoria...")
        inv, ver = await _rodar_caso(caso["pergunta"], sem_memoria=False)

        rca_corr = _rca_correctness(inv.relatorio or "", caso.get("expected_keywords", []))
        forb = _forbidden_avoidance(inv.relatorio or "", caso.get("forbidden_keywords", []))
        ev_cov = _evidence_coverage(inv.evidencias, caso.get("evidencias_minimas", []))
        crit = _critic_alignment(ver, caso.get("critic_aprovado", True))
        deg = _degraded_ratio(inv.evidencias)
        improv = _memory_improvement(iter_sem, redel_sem, inv.iteracao, inv.redelegacoes)

        recuperados = _achatar_recuperados(getattr(inv, "contexto_memoria", {}) or {})
        esperados = _esperados_unificados(caso)
        ret_prec = _calc_precision(recuperados, esperados)
        ret_rec = _calc_recall(recuperados, esperados)

        cliente_ok = (inv.cliente is not None
                      and inv.cliente.get("nome") == caso.get("cliente_esperado"))

        resultado = {
            "id": cid,
            "pergunta": caso["pergunta"],
            "cliente_esperado": caso.get("cliente_esperado"),
            "cliente_encontrado": inv.cliente.get("nome") if inv.cliente else None,
            "cliente_ok": cliente_ok,
            "confianca": round(inv.confianca, 3),
            "min_confianca": caso.get("min_confianca", 0.0),
            "iteracoes_sem": iter_sem,
            "iteracoes_com": inv.iteracao,
            "redelegacoes_sem": redel_sem,
            "redelegacoes_com": inv.redelegacoes,
            "n_evidencias": len(inv.evidencias),
            "critic_aprovado_obtido": ver.aprovado if ver else None,
            "critic_aprovado_esperado": caso.get("critic_aprovado"),
            "rca_correctness": round(rca_corr, 3),
            "forbidden_avoidance": round(forb, 3),
            "evidence_coverage": round(ev_cov, 3),
            "critic_alignment": round(crit, 3),
            "degraded_ratio": round(deg, 3),
            "memory_improvement": round(improv, 3),
            "retrieval_precision": round(ret_prec, 3),
            "retrieval_recall": round(ret_rec, 3),
            "n_recuperados": len(recuperados),
            "n_esperados": len(esperados),
        }
        resultados.append(resultado)

        print(
            f"  corr={rca_corr:.2f} forb={forb:.2f} cov={ev_cov:.2f} "
            f"crit={crit:.2f} deg={deg:.2f} improv={improv:.2f} "
            f"ret_p={ret_prec:.2f} ret_r={ret_rec:.2f} "
            f"(iter sem={iter_sem} com={inv.iteracao})"
        )

    # ------------------ Agregacao ------------------
    def _media(chave: str) -> float:
        vals = [r[chave] for r in resultados if chave in r]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    metricas = [
        "rca_correctness", "forbidden_avoidance", "evidence_coverage",
        "critic_alignment", "degraded_ratio", "memory_improvement",
        "retrieval_precision", "retrieval_recall",
    ]
    agregadas = {m: _media(m) for m in metricas}

    status = {}
    for m, valor in agregadas.items():
        if m not in thresholds:
            status[m] = "N/A"
            continue
        limiar = thresholds[m]
        if m == "degraded_ratio":
            status[m] = "PASS" if valor <= limiar else "FAIL"
        else:
            status[m] = "PASS" if valor >= limiar else "FAIL"

    tempo_total = round(time.time() - inicio, 1)

    # ------------------ Tabela final ------------------
    print(f"\n\n{'=' * 60}")
    print(f"  RESULTADO FINAL")
    print(f"{'=' * 60}")
    print(f"\n  {'Metrica':<24} {'Valor':>8} {'Threshold':>10} {'Status':>8}")
    print(f"  {'-' * 24} {'-' * 8} {'-' * 10} {'-' * 8}")
    for m in metricas:
        val = agregadas[m]
        thr = thresholds.get(m, "—")
        st = status.get(m, "N/A")
        print(f"  {m:<24} {val:>8.3f} {str(thr):>10} {st:>8}")

    aprovados = sum(1 for s in status.values() if s == "PASS")
    falhados = sum(1 for s in status.values() if s == "FAIL")
    print(f"\n  Resumo: {aprovados} PASS / {falhados} FAIL / {len(status) - aprovados - falhados} N/A")
    print(f"  Tempo total: {tempo_total}s")

    # ------------------ Relatorio markdown ------------------
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    relatorio_md = _gerar_relatorio_md(agregadas, thresholds, status, resultados, tempo_total)
    saida = ROOT / "reports" / "evals"
    saida.mkdir(parents=True, exist_ok=True)
    arq = saida / f"sentinel_impact_report_{ts}.md"
    arq.write_text(relatorio_md, encoding="utf-8")
    print(f"\n  Relatorio: {arq}\n")

    return {
        "tempo_total_segundos": tempo_total,
        "metricas_agregadas": agregadas,
        "thresholds": thresholds,
        "status": status,
        "resultados_por_caso": resultados,
        "arquivo_relatorio": str(arq),
    }


def _gerar_relatorio_md(agregadas, thresholds, status, resultados, tempo_total) -> str:
    md = []
    md.append("# Relatorio de Impacto — Multi-Agent Sentinel")
    md.append("")
    md.append(f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Casos avaliados:** {len(resultados)}")
    md.append(f"**Tempo total:** {tempo_total}s")
    md.append("")

    md.append("## Metricas Agregadas")
    md.append("")
    md.append("| Metrica | Valor | Threshold | Status |")
    md.append("|---------|-------|-----------|--------|")
    for m in ["rca_correctness", "forbidden_avoidance", "evidence_coverage",
              "critic_alignment", "degraded_ratio", "memory_improvement",
              "retrieval_precision", "retrieval_recall"]:
        val = agregadas.get(m, 0)
        thr = thresholds.get(m, "—")
        st = status.get(m, "N/A")
        md.append(f"| {m} | {val:.3f} | {thr} | {st} |")
    md.append("")

    md.append("## Comparativo: Sem vs Com Memoria")
    md.append("")
    md.append("| Caso | Iter Sem | Iter Com | Redel Sem | Redel Com | Improvement |")
    md.append("|------|----------|----------|-----------|-----------|-------------|")
    for r in resultados:
        md.append(
            f"| {r['id']} | {r['iteracoes_sem']} | {r['iteracoes_com']} | "
            f"{r['redelegacoes_sem']} | {r['redelegacoes_com']} | {r['memory_improvement']:.2f} |"
        )
    md.append("")

    md.append("## Detalhamento por Caso")
    md.append("")
    md.append("| Caso | Cliente OK | Conf | Evid | Corr | Forb | Cov | Crit | Deg |")
    md.append("|------|------------|------|------|------|------|-----|------|-----|")
    for r in resultados:
        md.append(
            f"| {r['id']} | {'✓' if r['cliente_ok'] else '✗'} | "
            f"{r['confianca']:.2f} | {r['n_evidencias']} | "
            f"{r['rca_correctness']:.2f} | {r['forbidden_avoidance']:.2f} | "
            f"{r['evidence_coverage']:.2f} | {r['critic_alignment']:.2f} | "
            f"{r['degraded_ratio']:.2f} |"
        )
    md.append("")

    aprov = sum(1 for s in status.values() if s == "PASS")
    falhou = sum(1 for s in status.values() if s == "FAIL")
    md.append("## Conclusao")
    md.append("")
    md.append(f"- {aprov} metricas aprovadas, {falhou} reprovadas")
    if agregadas.get("memory_improvement", 0) == 0:
        md.append("- `memory_improvement` = 0: camada de memoria ainda nao plugada (esperado nesta fase — baseline estabelecido)")
    if agregadas.get("degraded_ratio", 0) > 0.5:
        md.append("- `degraded_ratio` alto: provavel execucao sem MCPs reais. Verifique OPENROUTER_API_KEY / GRAFANA_API_KEY")
    if falhou == 0:
        md.append("- Todas as metricas dentro dos limiares — release candidate")
    md.append("")

    return "\n".join(md)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sentinel Impact Eval")
    parser.add_argument(
        "--suite",
        default=str(ROOT / "evals" / "suites" / "sentinel_impact_eval.yaml"),
        help="Caminho da suite YAML",
    )
    parser.add_argument("--max-casos", type=int, default=None, help="Limita N primeiros casos")
    parser.add_argument(
        "--skip-sem-memoria",
        action="store_true",
        help="Pula execucao baseline (sem memoria). Util enquanto memoria nao esta plugada.",
    )
    args = parser.parse_args()

    asyncio.run(executar_eval(Path(args.suite).resolve(), args.max_casos, args.skip_sem_memoria))


if __name__ == "__main__":
    main()
