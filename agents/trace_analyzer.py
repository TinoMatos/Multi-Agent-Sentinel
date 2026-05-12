"""Trace analyzer: lê data/traces/*.json e reporta KPIs do sistema.

Determinístico — não usa LLM. Responde:
- taxa de aprovação do Critic
- confiança média
- iterações/re-delegações
- % de evidências degradadas
- ferramentas/clientes mais frequentes

Uso:
    python -m agents.trace_analyzer
    python -m agents.trace_analyzer --traces /caminho/alternativo
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TRACES_DIR = ROOT / "data" / "traces"


@dataclass
class KPIs:
    total: int
    aprovados: int
    vetados: int
    confianca_media: float
    iteracao_media: float
    redelegacoes_total: int
    evidencias_total: int
    evidencias_degradadas: int
    por_cliente: dict[str, int]
    por_tipo_evidencia: dict[str, int]
    motivos_veto_mais_comuns: dict[str, int]
    backlogs_gerados: int = 0

    def relatorio(self) -> str:
        if self.total == 0:
            return "Nenhum trace encontrado."
        pct_aprovado = 100 * self.aprovados / self.total
        pct_degradado = (
            100 * self.evidencias_degradadas / self.evidencias_total
            if self.evidencias_total else 0
        )
        linhas = [
            f"# Trace Analyzer — {self.total} execucao(oes)",
            "",
            f"- Aprovados pelo Critic: {self.aprovados}/{self.total} ({pct_aprovado:.0f}%)",
            f"- Vetados pelo Critic:   {self.vetados}/{self.total}",
            f"- Confianca media:       {self.confianca_media:.0%}",
            f"- Iteracoes (media):     {self.iteracao_media:.1f}",
            f"- Re-delegacoes total:   {self.redelegacoes_total}",
            f"- Evidencias degradadas: {self.evidencias_degradadas}/{self.evidencias_total} ({pct_degradado:.0f}%)",
            f"- Backlogs gerados:      {self.backlogs_gerados}/{self.aprovados}",
            "",
            "## Por cliente",
        ]
        for nome, n in sorted(self.por_cliente.items(), key=lambda x: -x[1]):
            linhas.append(f"- {nome}: {n}")
        linhas += ["", "## Tipos de evidencia"]
        for tipo, n in sorted(self.por_tipo_evidencia.items(), key=lambda x: -x[1]):
            linhas.append(f"- {tipo}: {n}")
        if self.motivos_veto_mais_comuns:
            linhas += ["", "## Motivos de veto"]
            for motivo, n in sorted(self.motivos_veto_mais_comuns.items(), key=lambda x: -x[1]):
                linhas.append(f"- ({n}x) {motivo}")
        return "\n".join(linhas)


def analisar(traces_dir: Path = TRACES_DIR) -> KPIs:
    if not traces_dir.exists():
        return KPIs(0, 0, 0, 0.0, 0.0, 0, 0, 0, {}, {}, {})

    traces: list[dict[str, Any]] = []
    for path in traces_dir.glob("trace_*.json"):
        try:
            traces.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue

    if not traces:
        return KPIs(0, 0, 0, 0.0, 0.0, 0, 0, 0, {}, {}, {})

    aprovados = sum(1 for t in traces if t.get("veredito_aprovado"))
    backlogs = sum(1 for t in traces if t.get("backlog_path"))
    confiancas = [float(t.get("confianca") or 0) for t in traces]
    iteracoes = [int(t.get("iteracao") or 0) for t in traces]
    redelegacoes = sum(int(t.get("redelegacoes") or 0) for t in traces)

    evidencias_total = 0
    evidencias_degradadas = 0
    por_tipo: dict[str, int] = {}
    for t in traces:
        for e in t.get("evidencias", []) or []:
            evidencias_total += 1
            if e.get("degradado"):
                evidencias_degradadas += 1
            tipo = e.get("tipo") or "?"
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1

    por_cliente: dict[str, int] = {}
    for t in traces:
        nome = t.get("cliente") or "desconhecido"
        por_cliente[nome] = por_cliente.get(nome, 0) + 1

    motivos: dict[str, int] = {}
    for t in traces:
        if t.get("veredito_aprovado"):
            continue
        for m in t.get("veredito_motivos") or []:
            chave = str(m)[:80]
            motivos[chave] = motivos.get(chave, 0) + 1

    return KPIs(
        total=len(traces),
        aprovados=aprovados,
        vetados=len(traces) - aprovados,
        confianca_media=mean(confiancas),
        iteracao_media=mean(iteracoes),
        redelegacoes_total=redelegacoes,
        evidencias_total=evidencias_total,
        evidencias_degradadas=evidencias_degradadas,
        por_cliente=por_cliente,
        por_tipo_evidencia=por_tipo,
        motivos_veto_mais_comuns=motivos,
        backlogs_gerados=backlogs,
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Analisa traces do Multi-Agent Sentinel")
    p.add_argument("--traces", type=Path, default=TRACES_DIR, help="Pasta de traces JSON")
    args = p.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(analisar(args.traces).relatorio())
    return 0


if __name__ == "__main__":
    sys.exit(main())
