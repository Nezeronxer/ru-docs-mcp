from ru_docs import store
from ru_docs.ingest import chunk_markdown


def test_search_russian_wordforms(tmp_path):
    db = store.connect(tmp_path / "t.db")
    lib = {"id": "yookassa", "name": "ЮKassa", "aliases": ["юкасса"], "description": "", "homepage": "", "license": ""}
    md = ("# Платежи\n\n## Уведомления о возвратах\nЮKassa отправляет HTTP-уведомление на ваш URL "
          "при изменении статуса возврата.\n\n## Создание платежа\nPOST /v3/payments с заголовком Idempotence-Key.")
    store.replace_library(db, lib, chunk_markdown(md, "https://example/p"))

    hit = store.search(db, "уведомление возврата", lib="yookassa")[0]
    assert "возвратах" in hit["title"]
    # camelCase и заголовок находятся по частям слова
    assert "Создание" in store.search(db, "idempotence key создать платёж")[0]["title"]
    # повторная заливка заменяет, а не дублирует
    store.replace_library(db, lib, chunk_markdown(md, "https://example/p"))
    assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == len(chunk_markdown(md, "x"))


def test_compound_name_also_searched_as_phrase():
    assert store.fts_query("crm.deal.add оплата") == '"crm deal add" OR "crm" OR "deal" OR "add" OR "оплат"'


def test_identifier_in_title_beats_short_neighbours(tmp_path):
    db = store.connect(tmp_path / "t.db")
    lib = {"id": "b24", "name": "Б24", "aliases": [], "description": "", "homepage": "", "license": ""}
    md = ("# Создать шаблон crm.deal.recurring.add\n\nОшибка: deal add не найден, повторите crm deal add позже.\n\n"
          "# Создать сделку crm.deal.add\n\n" + "Поле TITLE задаёт название сделки, OPPORTUNITY сумму. " * 30)
    store.replace_library(db, lib, chunk_markdown(md, "u"))
    assert store.search(db, "crm.deal.add", lib="b24")[0]["title"] == "Создать сделку crm.deal.add"
