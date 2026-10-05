import pytest

from ru_docs import server, store
from ru_docs.ingest import chunk_markdown


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    db = store.connect(store.DB_PATH)
    tb = {"id": "tbank-eacq", "name": "Т-Банк", "aliases": ["тинькофф", "т-банк"],
          "description": "эквайринг", "homepage": "", "license": "грабли"}
    ssl = {"id": "1c-ssl", "name": "БСП", "aliases": ["бсп", "1с"], "description": "общие модули", "homepage": "",
           "license": "CC-BY-4.0"}
    store.replace_library(db, tb, chunk_markdown(
        "## Token: SHA-256 от отсортированных значений\nКорневые поля по алфавиту ключа, плюс Password.", "u1"),
        kind="gotcha")
    docs = "\n\n".join(f"## Метод {i}\nInit создаёт платёж, сумма в копейках. " + "текст " * 400 for i in range(20))
    store.replace_library(db, tb, chunk_markdown(docs, "u2"))
    store.replace_library(db, ssl, chunk_markdown("## ОбщегоНазначения.ЗначениеРеквизитаОбъекта\nчтение реквизита", "u3"))
    return db


def test_resolve_library():
    assert server.resolve_library("тинькофф").startswith("- id: tbank-eacq")
    assert server.resolve_library("бсп").startswith("- id: 1c-ssl")
    everything = server.resolve_library("")
    assert "tbank-eacq" in everything and "1c-ssl" in everything


def test_get_docs_gotchas_first_and_budget():
    out = server.get_docs("tbank-eacq", "token подпись init", tokens=1000)
    assert out.index("Грабли по теме") < out.index("## Документация")
    assert "SHA-256" in out
    assert len(out) < 1000 * server.CHARS_PER_TOKEN + 4000  # бюджет + последний блок грабель/шапка


def test_unknown_library_lists_ids():
    out = server.get_docs("tinkoff", "оплата")
    assert "Нет библиотеки" in out and "tbank-eacq" in out


def test_get_gotchas():
    assert "SHA-256" in server.get_gotchas("tbank-eacq")
    assert "SHA-256" in server.get_gotchas("tbank-eacq", "token")
    assert "точных совпадений нет" in server.get_gotchas("tbank-eacq", "холдирование")
    assert "пока нет" in server.get_gotchas("1c-ssl")
