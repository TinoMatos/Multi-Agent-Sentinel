from agents import analista


def test_cliente_por_nome_case_insensitive(mongo_seed):
    c = analista.cliente_por_nome("acme")
    assert c is not None
    assert c["_id"] == mongo_seed["acme_id"]


def test_cliente_por_nome_inexistente():
    assert analista.cliente_por_nome("Inexistente SA") is None


def test_tickets_abertos_do_cliente(mongo_seed):
    tickets = analista.tickets_abertos_do_cliente(mongo_seed["acme_id"])
    assert len(tickets) == 1
    assert tickets[0]["status"] == "aberto"


def test_erros_do_ticket(mongo_seed):
    ticket = mongo_seed["db"].tickets.find_one({"_id": mongo_seed["ticket_id"]})
    erros = analista.erros_do_ticket(ticket)
    assert len(erros) == 1
    assert erros[0]["tipo"] == "HTTP_500"


def test_registrar_rca_fecha_ticket(mongo_seed):
    rca_id = analista.registrar_rca(
        mongo_seed["ticket_id"],
        "deploy a1b2 causou regressao",
        [{"tipo": "commit", "ref": "a1b2", "nota": "x"}],
    )
    assert rca_id is not None
    ticket = mongo_seed["db"].tickets.find_one({"_id": mongo_seed["ticket_id"]})
    assert ticket["status"] == "fechado"
    assert ticket["rca_gerado_id"] == rca_id
    rca = mongo_seed["db"].rcas.find_one({"_id": rca_id})
    assert rca["conclusao"] == "deploy a1b2 causou regressao"
