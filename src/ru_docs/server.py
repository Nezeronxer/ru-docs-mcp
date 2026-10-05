"""MCP-сервер: документация российских платёжек, чеков 54-ФЗ, мессенджеров и 1С + грабли.

Работает локально (stdio). Индекс лежит в ~/.local/share/ru-docs/; если его нет или он старше
недели, сервер сам запускает сборку в фоне и отвечает по тому, что уже собрано.
"""
import subprocess
import sys
import time

from mcp.server.mcpserver import MCPServer

from . import store

REFRESH_DAYS = 7
CHARS_PER_TOKEN = 3  # грубо для смеси кириллицы и кода

mcp = MCPServer(
    "ru-docs",
    instructions=(
        "Документация российских сервисов: ЮKassa, ЮMoney, Т-Банк, CloudPayments, Robokassa, PayKeeper, "
        "платежи в Telegram, АТОЛ Онлайн, OrangeData, МАКС, VK API, Яндекс Мессенджер, БСП 1С. "
        "Перед кодом интеграции: resolve_library -> get_docs. Грабли в начале ответа get_docs - "
        "проверенные ловушки, их учитывать обязательно."
    ),
)


def _db():
    return store.connect()


def _status_note(db) -> str:
    log = store.DATA / "ingest.log"
    if not store.libraries(db):
        return ("Индекс ещё собирается (первый запуск, несколько минут). "
                f"Прогресс: {log}. Повторите запрос чуть позже.")
    return ""


def _lib_or_error(db, library_id: str):
    row = db.execute("SELECT * FROM libraries WHERE id=?", (library_id,)).fetchone()
    if row:
        return row, None
    ids = ", ".join(r["id"] for r in store.libraries(db))
    return None, f"Нет библиотеки «{library_id}». {_status_note(db)} Доступны: {ids}. Найти id: resolve_library."


def _fmt(r) -> str:
    return f"### {r['title']}\nИсточник: {r['url']}\n\n{r['body']}\n"


@mcp.tool()
def resolve_library(query: str = "") -> str:
    """Найти id библиотеки по названию сервиса (по-русски или по-английски): «юкасса», «тинькофф», «макс бот», «1с бсп».
    Пустой запрос - список всех библиотек."""
    db = _db()
    libs = store.libraries(db)
    if not libs:
        return _status_note(db)
    q = query.lower().replace("ё", "е").strip()
    qs = set(store.stems(q))
    scored = []
    for l in libs:
        names = [l["id"], l["name"].lower()] + l["aliases"].lower().split("|")
        score = 0 if q else 1
        if q:
            score += 10 * any(n and (n in q or q in n) for n in names)
            score += len(qs & set(store.stems(f"{l['name']} {l['aliases']} {l['description']}")))
        if score:
            scored.append((score, l))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return "Ничего не найдено. Все библиотеки: " + ", ".join(f"{l['id']} ({l['name']})" for l in libs)
    out = []
    for _, l in scored[:5]:
        g = db.execute("SELECT count(*) FROM chunks WHERE lib=? AND kind='gotcha'", (l["id"],)).fetchone()[0]
        out.append(f"- id: {l['id']}\n  {l['name']}: {l['description']}\n  фрагментов: {l['chunks']}, грабель: {g}, "
                   f"обновлено: {l['updated']}")
    return "\n".join(out)


@mcp.tool()
def get_docs(library_id: str, topic: str, tokens: int = 5000) -> str:
    """Фрагменты документации по теме (topic - своими словами, можно по-русски: «вебхук возврата», «чек 54-ФЗ»).
    Первым блоком идут грабли - проверенные ловушки по теме. tokens - бюджет ответа."""
    db = _db()
    lib, err = _lib_or_error(db, library_id)
    if err:
        return err
    budget = max(1000, min(tokens, 20000)) * CHARS_PER_TOKEN
    parts = [f"# {lib['name']}\nЛицензия/атрибуция: {lib['license']}. Сверяйте детали по ссылкам «Источник».\n"]
    gotchas = store.search(db, topic, lib=library_id, kind="gotcha", limit=3)
    if gotchas:
        parts.append("## ⚠ Грабли по теме\n" + "\n".join(_fmt(r) for r in gotchas))
    seen = set()
    parts.append("## Документация")
    for r in store.search(db, topic, lib=library_id, kind="doc", limit=40):
        key = (r["title"], r["body"][:200])
        if key in seen:
            continue
        seen.add(key)
        block = _fmt(r)
        if sum(map(len, parts)) + len(block) > budget:
            break
        parts.append(block)
    if len(parts) == 3 and not gotchas:
        parts.append("По этой теме ничего не нашлось - переформулируйте (синонимы, название метода, поле API).")
    return "\n".join(parts)


@mcp.tool()
def get_gotchas(library_id: str, topic: str = "") -> str:
    """Грабли по библиотеке: неочевидные ловушки интеграции (подписи, идемпотентность, копейки, тестовый режим, чеки).
    Без topic - все."""
    db = _db()
    lib, err = _lib_or_error(db, library_id)
    if err:
        return err
    rows = (store.search(db, topic, lib=library_id, kind="gotcha", limit=10) if topic.strip() else
            db.execute("SELECT * FROM chunks WHERE lib=? AND kind='gotcha' ORDER BY id", (library_id,)).fetchall())
    if not rows:
        return f"Грабель по «{lib['name']}»{' на тему ' + topic if topic else ''} пока нет."
    return "\n".join(_fmt(r) for r in rows)


def _maybe_refresh() -> None:
    """Нет индекса или он старше недели - пересобрать в фоне отдельным процессом."""
    db = _db()
    row = db.execute("SELECT min(strftime('%s', updated)) FROM libraries").fetchone()[0]
    if row and time.time() - int(row) < REFRESH_DAYS * 86400:
        return
    lock = store.DATA / "ingest.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < 3600:
        return  # сборка уже идёт
    lock.touch()
    log = open(store.DATA / "ingest.log", "w")
    subprocess.Popen([sys.executable, "-u", "-m", "ru_docs.ingest", "--lock", str(lock)],
                     stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)


def main():
    _maybe_refresh()
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
