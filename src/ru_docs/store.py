"""SQLite FTS5 с русским и английским стеммингом.

В FTS5 нет русского стеммера, поэтому стеммим сами: в индекс кладём основы слов,
а исходный текст храним рядом для выдачи.
"""
import os
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

import snowballstemmer

DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ru-docs"
DB_PATH = Path(os.environ.get("RU_DOCS_DB", DATA / "ru-docs.db"))

_ru = snowballstemmer.stemmer("russian")
_en = snowballstemmer.stemmer("english")
_word = re.compile(r"[0-9a-zа-яё_]+", re.I)
_part = re.compile(r"[A-ZА-Я]?[a-zа-я]+|[A-ZА-Я]+(?![a-zа-я])|[0-9]+")


@lru_cache(maxsize=200_000)
def _stem(w: str) -> str:
    if w.isdigit():
        return w
    return _ru.stemWord(w) if re.search("[а-я]", w) else _en.stemWord(w)


def stems(text: str) -> list[str]:
    out = []
    for w in _word.findall(text.replace("ё", "е").replace("Ё", "Е")):
        out.append(_stem(w.lower()))
        # camelCase и snake_case: PaymentId -> payment, id; return_url -> return, url
        parts = _part.findall(w)
        if len(parts) > 1:
            out.extend(_stem(p.lower()) for p in parts)
    return out


SCHEMA = """
CREATE TABLE IF NOT EXISTS libraries(
  id TEXT PRIMARY KEY, name TEXT, aliases TEXT, description TEXT,
  homepage TEXT, license TEXT, chunks INTEGER DEFAULT 0, updated TEXT);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY, lib TEXT, kind TEXT, title TEXT, url TEXT, body TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(title, body, content='', contentless_delete=1);
CREATE INDEX IF NOT EXISTS chunks_lib ON chunks(lib, kind);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")  # сервер читает, пока ingest пишет
    db.executescript(SCHEMA)
    return db


def replace_library(db, lib: dict, chunks: list[dict], kind: str = "doc") -> int:
    """Атомарно заменяет чанки одного вида у библиотеки. chunks: [{title, url, body}]."""
    with db:
        old = [r[0] for r in db.execute("SELECT id FROM chunks WHERE lib=? AND kind=?", (lib["id"], kind))]
        db.executemany("DELETE FROM chunks_fts WHERE rowid=?", [(i,) for i in old])
        db.execute("DELETE FROM chunks WHERE lib=? AND kind=?", (lib["id"], kind))
        for c in chunks:
            cur = db.execute("INSERT INTO chunks(lib, kind, title, url, body) VALUES (?,?,?,?,?)",
                             (lib["id"], kind, c["title"], c["url"], c["body"]))
            db.execute("INSERT INTO chunks_fts(rowid, title, body) VALUES (?,?,?)",
                       (cur.lastrowid, " ".join(stems(c["title"])), " ".join(stems(c["body"]))))
        db.execute("""INSERT INTO libraries(id, name, aliases, description, homepage, license, updated)
                      VALUES (:id, :name, :aliases, :description, :homepage, :license, datetime('now'))
                      ON CONFLICT(id) DO UPDATE SET name=excluded.name, aliases=excluded.aliases,
                      description=excluded.description, homepage=excluded.homepage,
                      license=excluded.license, updated=excluded.updated""",
                   {**lib, "aliases": "|".join(lib.get("aliases", []))})
        db.execute("UPDATE libraries SET chunks=(SELECT count(*) FROM chunks WHERE lib=?) WHERE id=?",
                   (lib["id"], lib["id"]))
    return len(chunks)


def fts_query(text: str) -> str | None:
    terms = list(dict.fromkeys(stems(text)))
    # составное имя (crm.deal.add, Idempotence-Key) ещё и фразой - точный метод выше похожих
    phrases = [" ".join(s) for w in text.split() if len(s := stems(w)) > 1]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(phrases + terms)) or None


def search(db, text: str, lib: str | None = None, kind: str | None = None, limit: int = 20) -> list[sqlite3.Row]:
    q = fts_query(text)
    if not q:
        return []
    sql = """SELECT c.*, bm25(chunks_fts, 5.0, 1.0) AS rank FROM chunks_fts
             JOIN chunks c ON c.id = chunks_fts.rowid WHERE chunks_fts MATCH ?"""
    args: list = [q]
    if lib:
        sql += " AND c.lib = ?"
        args.append(lib)
    if kind:
        sql += " AND c.kind = ?"
        args.append(kind)
    sql += " ORDER BY rank LIMIT ?"
    args.append(limit)
    return db.execute(sql, args).fetchall()


def libraries(db) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM libraries ORDER BY id").fetchall()
