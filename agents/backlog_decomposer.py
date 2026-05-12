"""Backlog Decomposer: agente goal_oriented que transforma objetivo em backlog.

Recebe uma frase ampla ("permitir que novos usuarios completem cadastro sem
suporte humano") e devolve markdown com dominios, epicos, stories, riscos e
perguntas — encadeados na ordem 1→2→3→4→5→6 da aula06.

Modo LLM (com OPENROUTER_API_KEY): chamada estruturada unica.
Modo degradado (sem key): esqueleto deterministico baseado no proprio objetivo.

    python -m agents.backlog_decomposer "objetivo aqui"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any

from agents import _llm


SKILLS_ORDEM = [
    "analisar_objetivo",
    "gerar_epicos",
    "detalhar_stories",
    "avaliar_riscos",
    "gerar_perguntas",
    "montar_backlog",
]


@dataclass
class Backlog:
    objetivo: str
    dominios: list[str] = field(default_factory=list)
    epicos: list[dict[str, Any]] = field(default_factory=list)
    riscos: list[str] = field(default_factory=list)
    perguntas: list[str] = field(default_factory=list)
    modo: str = "deterministico"

    def render(self) -> str:
        linhas = [
            f"# Backlog — {self.objetivo}",
            "",
            f"_Gerado em modo `{self.modo}`. Skills aplicadas: {' -> '.join(SKILLS_ORDEM)}_",
            "",
            "## Dominios identificados",
        ]
        linhas += [f"- {d}" for d in self.dominios] or ["- (nenhum)"]
        linhas += ["", "## Epicos e stories"]
        for i, ep in enumerate(self.epicos, 1):
            linhas.append(f"\n### Epico {i}: {ep['titulo']}")
            for s in ep.get("stories", []):
                criterio = s.get("criterio_aceite") or "?"
                linhas.append(f"- **{s['titulo']}** — criterio: {criterio}")
        linhas += ["", "## Riscos"]
        linhas += [f"- {r}" for r in self.riscos] or ["- (nenhum identificado)"]
        linhas += ["", "## Perguntas de esclarecimento"]
        linhas += [f"- {q}" for q in self.perguntas] or ["- (objetivo claro o suficiente)"]
        return "\n".join(linhas) + "\n"


_SYSTEM = (
    "Voce e um agente goal_oriented que decompoe objetivos de produto em "
    "backlog executavel. Aplique as 6 skills na ordem fixa: "
    "analisar_objetivo -> gerar_epicos -> detalhar_stories -> avaliar_riscos -> "
    "gerar_perguntas -> montar_backlog. Devolva APENAS JSON puro (sem markdown, "
    "sem ```json) com as chaves: dominios (lista de string, 2-4 itens), "
    "epicos (lista de objeto com titulo:string e stories:lista de "
    "{titulo:string, criterio_aceite:string}, 2-4 epicos, 2-3 stories cada), "
    "riscos (lista de string, 3-5 itens), perguntas (lista de string, 2-4 itens)."
)


def _decompor_deterministico(objetivo: str) -> Backlog:
    """Esqueleto deterministico — quebra o objetivo em palavras-chave."""
    palavras = [p for p in re.split(r"\W+", objetivo.lower()) if len(p) >= 4]
    chave = palavras[0] if palavras else "objetivo"
    return Backlog(
        objetivo=objetivo,
        dominios=["fluxo de usuario", "infraestrutura", "observabilidade"],
        epicos=[
            {
                "titulo": f"Fluxo principal de {chave}",
                "stories": [
                    {"titulo": "Definir jornada feliz", "criterio_aceite": "diagrama validado com produto"},
                    {"titulo": "Implementar caminho mais comum", "criterio_aceite": "teste e2e passa"},
                ],
            },
            {
                "titulo": "Tratamento de erros e bordas",
                "stories": [
                    {"titulo": "Mapear estados de falha", "criterio_aceite": "lista de erros com mensagem ao usuario"},
                    {"titulo": "Implementar retry/recuperacao", "criterio_aceite": "usuario nao fica preso"},
                ],
            },
            {
                "titulo": "Observabilidade do fluxo",
                "stories": [
                    {"titulo": "Instrumentar metricas chave", "criterio_aceite": "dashboard com taxa de sucesso"},
                ],
            },
        ],
        riscos=[
            "escopo amplo demais — precisa fatiar antes de comprometer prazo",
            "dependencia oculta com sistemas legados pode aparecer tarde",
            "falta de criterio claro de 'pronto' para o objetivo amplo",
        ],
        perguntas=[
            f"Qual e o publico-alvo concreto do objetivo '{objetivo}'?",
            "Existe metrica de sucesso ja acordada?",
            "Ha restricao de prazo, compliance ou orcamento que limita o escopo?",
        ],
        modo="deterministico",
    )


async def _decompor_llm(objetivo: str) -> Backlog | None:
    llm = _llm.fast()
    if llm is None:
        return None
    try:
        resp = await llm.ainvoke(f"{_SYSTEM}\n\nOBJETIVO: {objetivo}")
        texto = resp.content if isinstance(resp.content, str) else str(resp.content)
        bruto = texto[texto.find("{") : texto.rfind("}") + 1]
        data = json.loads(bruto)
        return Backlog(
            objetivo=objetivo,
            dominios=[str(d) for d in data.get("dominios", [])],
            epicos=[
                {
                    "titulo": str(ep.get("titulo", "?")),
                    "stories": [
                        {
                            "titulo": str(s.get("titulo", "?")),
                            "criterio_aceite": str(s.get("criterio_aceite", "?")),
                        }
                        for s in ep.get("stories", [])
                    ],
                }
                for ep in data.get("epicos", [])
            ],
            riscos=[str(r) for r in data.get("riscos", [])],
            perguntas=[str(q) for q in data.get("perguntas", [])],
            modo="llm",
        )
    except Exception:
        return None


async def decompor(objetivo: str) -> Backlog:
    """Decompoe o objetivo em backlog. Tenta LLM, cai pra deterministico."""
    if _llm.disponivel():
        bl = await _decompor_llm(objetivo)
        if bl is not None:
            return bl
    return _decompor_deterministico(objetivo)


def main() -> int:
    import asyncio

    p = argparse.ArgumentParser(description="Decompoe objetivo em backlog")
    p.add_argument("objetivo", nargs="+", help="Objetivo de produto a decompor")
    args = p.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    objetivo = " ".join(args.objetivo)
    backlog = asyncio.run(decompor(objetivo))
    print(backlog.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
