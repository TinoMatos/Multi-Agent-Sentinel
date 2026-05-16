"""Analista: consulta MongoDB para contexto de cliente, historico e correlacao.

Expoe funcoes puras (sem LLM) que a Triagem chama. A inteligencia de quando
chamar cada uma fica no orchestrator; aqui sao queries deterministicas.
"""
from __future__ import annotations

import os
import re
from typing import Any

from pymongo import MongoClient

_client: MongoClient | None = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/sentinel"))
    return _client.get_default_database()


def cliente_por_nome(nome: str) -> dict[str, Any] | None:
    return _db().clientes.find_one({"nome": {"$regex": re.escape(nome), "$options": "i"}})


def tickets_abertos_do_cliente(client_id) -> list[dict[str, Any]]:
    return list(_db().tickets.find({"clientId": client_id, "status": {"$ne": "fechado"}}))


def erros_do_ticket(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    ids = ticket.get("erros_correlacionados", [])
    return list(_db().erros.find({"_id": {"$in": ids}}))


def rcas_similares(
    stacktrace: str,
    limit: int = 3,
    client_id: Any = None,
    tipo_erro: str | None = None,
) -> list[dict[str, Any]]:
    """Busca RCAs com stacktrace similar, filtrando por cliente e/ou tipo.

    Sem `client_id`/`tipo_erro` o resultado pode trazer ruido cross-cliente
    (Acme aparecendo na investigacao da Gama). Sempre passe pelo menos um.
    """
    db = _db()
    erro_filter: dict[str, Any] = {}
    if tipo_erro:
        erro_filter["tipo"] = tipo_erro

    chave = stacktrace.split("\n", 1)[0][:80]
    try:
        query = {"$text": {"$search": stacktrace[:200]}, **erro_filter}
        cur = db.erros.find(
            query, {"score": {"$meta": "textScore"}, "ticket_relacionado": 1}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit * 3)
        ticket_ids = [e["ticket_relacionado"] for e in cur if e.get("ticket_relacionado")]
    except Exception:
        # fallback: substring naive (mongomock nao suporta $text + textScore)
        query = {"stacktrace": {"$regex": re.escape(chave[:40])}, **erro_filter}
        cur = db.erros.find(query).limit(limit * 3)
        ticket_ids = [e["ticket_relacionado"] for e in cur if e.get("ticket_relacionado")]
    if not ticket_ids:
        return []

    rca_query: dict[str, Any] = {"ticket_id": {"$in": ticket_ids}}
    if client_id is not None:
        # cruza: so traz RCAs cujo ticket pertence ao mesmo cliente
        tickets_do_cliente = list(db.tickets.find(
            {"_id": {"$in": ticket_ids}, "clientId": client_id}, {"_id": 1}
        ))
        ids_validos = [t["_id"] for t in tickets_do_cliente]
        if not ids_validos:
            return []
        rca_query["ticket_id"] = {"$in": ids_validos}

    return list(db.rcas.find(rca_query).limit(limit))


def registrar_rca(ticket_id, conclusao: str, evidencias: list[dict[str, Any]]) -> Any:
    from datetime import datetime, timezone

    from guards.output_guard import sanitize

    evidencias_safe = [
        {**e, "nota": sanitize(e["nota"]) if isinstance(e.get("nota"), str) else e.get("nota")}
        for e in evidencias
    ]
    rca = {
        "ticket_id": ticket_id,
        "conclusao": sanitize(conclusao),
        "evidencias": evidencias_safe,
        "gerado_em": datetime.now(timezone.utc),
    }
    rca_id = _db().rcas.insert_one(rca).inserted_id
    _db().tickets.update_one(
        {"_id": ticket_id},
        {"$set": {"rca_gerado_id": rca_id, "status": "fechado", "atualizado_em": rca["gerado_em"]}},
    )
    return rca_id
