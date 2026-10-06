import asyncio
import json
from types import SimpleNamespace

from ru_docs import ingest

SPEC = {
    "servers": [{"url": "https://api.example.ru/v3"}],
    "paths": {"/payments": {"post": {
        "summary": "Create a payment",
        "parameters": [{"$ref": "#/components/parameters/Idem"}],
        "requestBody": {"content": {"application/json": {"schema": {
            "required": ["quantity"],
            "properties": {
                "quantity": {"$ref": "#/components/schemas/Qty"},
                "amount": {"allOf": [{"$ref": "#/components/schemas/Money"}, {"description": "Цена товара"}]},
            }}}}},
    }}},
    "components": {
        "parameters": {"Idem": {"name": "Idempotence-Key", "in": "header", "required": True}},
        "schemas": {"Qty": {"type": "number", "description": "Количество"},
                    "Money": {"type": "object", "properties": {"value": {"type": "string"}}}},
    },
}


def test_openapi_resolves_server_path_parameter_and_property_refs(monkeypatch):
    async def fake_fetch(client, url):
        return SimpleNamespace(text=json.dumps(SPEC))
    monkeypatch.setattr(ingest, "fetch", fake_fetch)
    chunks = asyncio.run(ingest.load_openapi({"spec": "https://x/spec.json"}))
    op = next(c for c in chunks if c["title"].startswith("POST"))
    assert op["title"] == "POST /v3/payments — Create a payment"
    assert "`Idempotence-Key` (header) **обяз.**" in op["body"]
    assert "`quantity` number, схема Qty **обяз.** — Количество" in op["body"]
    assert "`amount` Money — Цена товара" in op["body"]


def test_github_md_drops_yfm_noise():
    md = ("# Создать сделку crm.deal.add\n\n{% include [Сноска](../_includes/examples.md) %}\n"
          "Метод создаёт новую сделку и возвращает её идентификатор в поле result.\n\n"
          "## Продолжите изучение\n\n- [{#T}](./crm-deal-update.md)\n- [{#T}](./crm-deal-get.md)\n")
    chunks = ingest._gh_md(md, "crm-deal-add.md", "u")
    assert len(chunks) == 1 and "{%" not in chunks[0]["body"]
