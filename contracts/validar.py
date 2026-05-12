"""Validador de contratos.

Cruza contracts/<agente>/{agent,rules,skills}.md com o código real.
Falha (exit 1) se houver divergência factual. Aviso (exit 0) se for só estilo.

    python -m contracts.validar
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
AGENTES = ["triagem", "tecnico", "analista", "observabilidade", "critic", "rca_writer", "trace_analyzer", "backlog_decomposer"]
TIPOS_VALIDOS = {"task_based", "interactive", "goal_oriented", "autonomous"}
ARQUIVOS_ESPERADOS = {"agent.md", "rules.md", "skills.md", "hooks.md", "memory.md"}


def extrair_yaml(md_path: Path) -> dict:
    texto = md_path.read_text(encoding="utf-8")
    match = re.search(r"```yaml\s*\n(.*?)\n```", texto, re.DOTALL)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def ler_default_env(py_path: Path, var: str) -> str | None:
    """Extrai default de os.getenv('VAR', 'default') no código."""
    pat = re.compile(rf'os\.getenv\(["\']{re.escape(var)}["\']\s*,\s*["\']([^"\']+)["\']\)')
    m = pat.search(py_path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def main() -> int:
    erros: list[str] = []
    avisos: list[str] = []

    # 1. estrutura: cada agente tem os 5 .md
    for agente in AGENTES:
        pasta = CONTRACTS / agente
        if not pasta.is_dir():
            erros.append(f"[{agente}] pasta não existe em contracts/")
            continue
        existentes = {p.name for p in pasta.glob("*.md")}
        for esperado in ARQUIVOS_ESPERADOS:
            if esperado not in existentes:
                erros.append(f"[{agente}] falta {esperado}")

    # 2. agent.md: nome casa com pasta, tipo é válido
    for agente in AGENTES:
        path = CONTRACTS / agente / "agent.md"
        if not path.exists():
            continue
        spec = extrair_yaml(path)
        nome = spec.get("nome")
        tipo = spec.get("tipo")
        if nome != agente:
            erros.append(f"[{agente}/agent.md] nome={nome!r} não bate com pasta {agente!r}")
        if tipo not in TIPOS_VALIDOS:
            erros.append(f"[{agente}/agent.md] tipo={tipo!r} inválido (use {sorted(TIPOS_VALIDOS)})")
        if not spec.get("contrato_saida", {}).get("campos_obrigatorios"):
            avisos.append(f"[{agente}/agent.md] contrato_saida.campos_obrigatorios vazio")

    # 3. rules vs código: limites bateram com os defaults reais
    bindings = [
        ("triagem", "max_etapas", ROOT / "guards/safeguards.py", "SENTINEL_MAX_ITERATIONS"),
        ("tecnico", "limite_tempo_segundos", ROOT / "agents/triagem.py", "SENTINEL_TECNICO_TIMEOUT_S"),
        ("observabilidade", "limite_tempo_segundos", ROOT / "agents/triagem.py", "SENTINEL_OBS_TIMEOUT_S"),
    ]
    for agente, chave_yaml, py_path, env_var in bindings:
        rules = extrair_yaml(CONTRACTS / agente / "rules.md")
        valor_contrato = rules.get("limites", {}).get(chave_yaml)
        valor_codigo = ler_default_env(py_path, env_var)
        if valor_codigo is None:
            avisos.append(f"[{agente}/rules.md] {env_var} não encontrado em {py_path.name}")
            continue
        if str(valor_contrato) != valor_codigo:
            erros.append(
                f"[{agente}/rules.md] {chave_yaml}={valor_contrato} diverge de "
                f"{env_var} default={valor_codigo} ({py_path.name})"
            )

    # 4. skills.md: nome de cada habilidade não pode estar vazio
    for agente in AGENTES:
        skills = extrair_yaml(CONTRACTS / agente / "skills.md")
        for i, h in enumerate(skills.get("habilidades", [])):
            if not h.get("nome"):
                erros.append(f"[{agente}/skills.md] habilidade #{i} sem nome")
            if not h.get("descricao"):
                avisos.append(f"[{agente}/skills.md] {h.get('nome', '?')} sem descricao")

    # 5. rules.acoes_sensiveis: cada item deve aparecer em skills.md ou no código
    for agente in AGENTES:
        rules = extrair_yaml(CONTRACTS / agente / "rules.md")
        skills = extrair_yaml(CONTRACTS / agente / "skills.md")
        nomes_skill = {h.get("nome") for h in skills.get("habilidades", [])}
        for acao in rules.get("acoes_sensiveis") or []:
            if acao in nomes_skill:
                continue
            # heurística: o nome aparece como def/função em algum .py?
            hit = False
            for py in (ROOT / "agents").glob("*.py"):
                if re.search(rf"\bdef\s+{re.escape(acao)}\b", py.read_text(encoding="utf-8")):
                    hit = True
                    break
            if not hit:
                avisos.append(
                    f"[{agente}/rules.md] ação sensível {acao!r} não está em skills.md nem como def em agents/*.py"
                )

    # relatório
    print(f"agentes verificados: {len(AGENTES)}")
    print(f"erros: {len(erros)}  avisos: {len(avisos)}\n")
    for a in avisos:
        print(f"  ! {a}")
    for e in erros:
        print(f"  X {e}")
    if erros:
        print("\nFAIL")
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
