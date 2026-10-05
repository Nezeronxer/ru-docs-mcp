## Итерация 2 (2026-10-05) - план `~/.claude/plans/frolicking-sparking-music.md`
- [x] 6 новых библиотек + ingest: yandex-pay, bitrix24, amocrm, dadata, smsru, gigachat (Почта - SPA, не берём). Яндекс Пэй и GigaChat - ещё и openapi-спеки; get_docs больше не отдаёт пусто, если первый фрагмент длиннее бюджета
- [x] Грабли для 7 старых: robokassa, yoomoney, paykeeper, orangedata, atol-online, yandex-messenger, 1c-ssl
- [x] Грабли для 6 новых (6 штук на библиотеку; 363 цитаты сверены с индексом и живыми страницами)
- [x] Тесты: test_gotchas.py, test_server.py (+ _db() читает store.DB_PATH при вызове; get_gotchas при пустом поиске по теме отдаёт все)
- [x] README, instructions сервера, скилл ru-docs, версия 0.2.0, .gitignore graphify-out
- [ ] GitHub: gh auth login (пользователь) -> repo create --public -> push -> проверка uvx

# ru-docs-mcp - чек-лист

План: `~/.claude/plans/immutable-singing-mountain.md`

- [x] Каркас uv-проекта (Python 3.12, mcp 2.x - там `MCPServer`, не FastMCP)
- [x] store.py: SQLite FTS5 + стемминг ru/en, тест
- [x] ingest.py: загрузчики openapi / html (urls, sitemap, crawl) / pdf / github (md, bsl) / vk_schema
- [x] sources.toml: 13 источников v1, ingest всех (у Т-Банка только грабли - сайт не отдаётся)
- [x] server.py: resolve_library, get_docs (грабли первым блоком), get_gotchas
- [x] gotchas/: ЮKassa, Т-Банк, CloudPayments, МАКС, Telegram-оплата, 54-ФЗ - сверены с доками
- [x] Живой тест через `claude mcp add` (локально, stdio)
- [x] Скилл `ru-docs` в ~/.claude/skills (вне репо)
- [x] git: первый коммит (автор Nezeronxer, без следов ИИ)
- [x] риг `ru_docs_mcp` (Gastown поставлен на Arch)
- [ ] Публичный GitHub - СПРОСИТЬ
- [ ] Dockerfile + деплой - СПРОСИТЬ сервер и домен
- [ ] Ролик через /shorts-week - показать перед заливкой

## Найдено по ходу
- У ЮKassa и Robokassa есть официальные OpenAPI (`yookassa.ru/developers/api/yookassa-openapi-specification.yaml`,
  `docs.robokassa.ru/openapi/robokassa.yaml`); у ЮKassa есть свой MCP-сервер (раздел «MCP-сервер ЮKassa»).
- Служба `moya-papka-sync` (Dropbox ↔ «Моя папка») унесла `pyproject.toml` в корзину после перезаписи uv
  (`~/.local/share/moya-papka/deleted/2026-10-04/...`). Восстановлен. Следить за файлами, которые переписывают инструменты.
- Отсюда не открываются developer.tbank.ru, Сбер, Альфа, botapi.messenger.yandex (curl 000).
- 2026-10-05: чистая установка `uvx --from git+file://...` с пустым XDG_DATA_HOME проверена - автосборка
  при первом запуске работает, 12 из 13 библиотек совпали с основным индексом.
- АТОЛ: online.atol.ru -> atol.online, на любой URL отдаётся антибот-заглушка (HTML 13 КБ, JS-проверка).
  Не обходим; в основном индексе остались 198 чанков от 04.10, у новых установок АТОЛа нет. README дополнен.
- README уже описывает только локальный режим («внешний сервер не нужен») - пункт «Dockerfile + деплой»
  под вопросом, решает пользователь.
