"""Auto-reseed: reabre tickets fechados pelo Sentinel sem precisar do mongosh.

Em vez de re-executar todo o seed.js (slow), reverte o estado dos tickets/RCAs
gerados nesta sessao. Idempotente — pode chamar antes de cada investigacao.
"""
from __future__ import annotations

from agents.analista import _db


def reset_tickets() -> dict[str, int]:
    """Reabre todos os tickets que o Sentinel fechou + apaga RCAs gerados.

    Retorna contadores: {"tickets_reabertos": N, "rcas_apagados": M}.
    """
    db = _db()
    # ticket "antigo" do seed (Erro 500 esporadico em /login - resolvido) deve ficar fechado
    res_tk = db.tickets.update_many(
        {"status": "fechado", "rca_gerado_id": {"$ne": None}, "descricao": {"$not": {"$regex": "resolvido"}}},
        {"$set": {"status": "aberto"}, "$unset": {"rca_gerado_id": ""}},
    )
    # apaga RCAs gerados pelo Sentinel (preserva os 2 historicos do seed)
    res_rca = db.rcas.delete_many({"origem": {"$ne": "historico"}})
    return {
        "tickets_reabertos": res_tk.modified_count,
        "rcas_apagados": res_rca.deleted_count,
    }
