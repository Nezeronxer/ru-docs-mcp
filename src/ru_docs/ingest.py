"""Сборка индекса: sources.toml -> загрузчики -> чанки -> SQLite.

uv run ru-docs-ingest            # все источники
uv run ru-docs-ingest max vk     # только эти
"""
import argparse
import asyncio
import fnmatch
import io
import json
import re
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import urljoin, urldefrag

import httpx
import yaml
from markdownify import markdownify
from pypdf import PdfReader
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from . import store

PKG = Path(__file__).resolve().parent
UA = "ru-docs-mcp/0.1 (docs index; +https://github.com/Nezeronxer/ru-docs-mcp)"
MAX_CHUNK = 3000

# ---------- общие куски ----------


def chunk_markdown(md: str, url: str, prefix: str = "") -> list[dict]:
    """Режет markdown по заголовкам 1-3 уровня; заголовок чанка - путь заголовков."""
    path: list[str] = [prefix] if prefix else []
    base = len(path)
    out, buf, title = [], [], prefix

    def flush():
        body = "\n".join(buf).strip()
        if len(body) >= 40:
            for part in _split(body):
                out.append({"title": title or url, "url": url, "body": part})
        buf.clear()

    for line in md.splitlines():
        m = re.match(r"^(#{1,3})\s+(.+?)\s*#*$", line)
        if m:
            flush()
            lvl = len(m[1])
            del path[base + lvl - 1:]
            path.append(m[2].strip())
            title = " › ".join(path)
        else:
            buf.append(line)
    flush()
    return out


def _split(body: str) -> list[str]:
    if len(body) <= MAX_CHUNK:
        return [body]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", body):
        if cur and len(cur) + len(para) > MAX_CHUNK:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
        while len(cur) > MAX_CHUNK * 2:  # огромный абзац (таблица) - режем грубо
            parts.append(cur[:MAX_CHUNK])
            cur = cur[MAX_CHUNK:]
    return parts + [cur] if cur else parts


def html_to_md(html: str, selector: str | None) -> str:
    tree = HTMLParser(html)
    for sel in ("script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form"):
        for n in tree.css(sel):
            n.decompose()
    node = None
    for sel in (selector or "main, article").split(","):
        node = tree.css_first(sel.strip())
        if node:
            break
    node = node or tree.body
    try:
        md = markdownify(node.html if node else "", heading_style="ATX", strip=["img"])
    except RecursionError:  # слишком глубокая вёрстка (PayKeeper) - хотя бы текст
        md = node.text(separator="\n") if node else ""
    return re.sub(r"\n{3,}", "\n\n", md)


async def fetch(client: httpx.AsyncClient, url: str) -> httpx.Response:
    for attempt in range(3):
        try:
            r = await client.get(url)
            r.raise_for_status()
            return r
        except httpx.HTTPError:
            if attempt == 2:
                raise
            await asyncio.sleep(2 * (attempt + 1))


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": UA}, follow_redirects=True, timeout=60)


# ---------- загрузчики: каждый возвращает список чанков ----------


async def load_html(src: dict) -> list[dict]:
    """Страницы из urls, sitemap и/или crawl (обход ссылок внутри префикса)."""
    async with _client() as c:
        urls = list(src.get("urls", []))
        if sm := src.get("sitemap"):
            xml = (await fetch(c, sm)).text
            urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
        inc, exc = src.get("include", []), src.get("exclude", [])
        urls = [u for u in dict.fromkeys(urls)
                if (not inc or any(p in u for p in inc)) and not any(p in u for p in exc)]
        sem = asyncio.Semaphore(4)
        pages: dict[str, str] = {}

        async def get(u):
            async with sem:
                try:
                    r = await fetch(c, u)
                    if "html" in r.headers.get("content-type", ""):  # PDF и архивы по ссылкам - мимо
                        pages[u] = r.text
                except httpx.HTTPError as e:
                    print(f"  ! {u}: {e}", file=sys.stderr)
                await asyncio.sleep(0.3)

        if start := src.get("crawl"):  # обход в ширину по ссылкам с тем же префиксом
            prefix, limit, seen, queue = src.get("prefix", start), src.get("max_pages", 300), {start}, [start]
            while queue and len(pages) < limit:
                batch, queue = queue[:8], queue[8:]
                await asyncio.gather(*(get(u) for u in batch))
                for u in batch:
                    tree = HTMLParser(pages.get(u, ""))
                    base = urljoin(u, (tree.css_first("base[href]") or tree.root).attributes.get("href") or "") if tree.root else u
                    for a in tree.css("a[href]"):
                        link = urldefrag(urljoin(base, a.attributes.get("href") or ""))[0]
                        if link.startswith(prefix) and link not in seen and not any(p in link for p in exc):
                            seen.add(link)
                            queue.append(link)
        await asyncio.gather(*(get(u) for u in urls if u not in pages))

    chunks = []
    for u, html in pages.items():
        t = HTMLParser(html).css_first("title")
        title = re.split(r"\s+[|—–-]\s+", t.text().strip())[0] if t else ""
        chunks += chunk_markdown(html_to_md(html, src.get("selector")), u, prefix=title)
    return chunks


async def load_openapi(src: dict) -> list[dict]:
    async with _client() as c:
        text = (await fetch(c, src["spec"])).text
    try:
        spec = yaml.safe_load(text)
    except yaml.YAMLError:  # у GigaChat табы в примерах - YAML их не прощает
        spec = yaml.safe_load(text.replace("\t", "  "))
    url = src.get("docs_url", src["spec"])
    schemas = spec.get("components", {}).get("schemas", {})
    chunks = []

    def ref_name(s):
        return s.get("$ref", "").rsplit("/", 1)[-1] if isinstance(s, dict) else ""

    def props(s, depth=0):
        if not isinstance(s, dict):
            return ""
        if (name := ref_name(s)) and depth < 1:
            return f"(схема {name})\n" + props(schemas.get(name, {}), depth + 1)
        lines, req = [], set(s.get("required", []))
        for k, v in (s.get("properties") or {}).items():
            t = v.get("type") or ref_name(v) or ("|".join(ref_name(x) or x.get("type", "") for x in v.get("oneOf", v.get("anyOf", []))))
            enum = f" [{', '.join(map(str, v['enum']))}]" if "enum" in v else ""
            desc = (v.get("description") or v.get("title") or "").strip().replace("\n", " ")
            lines.append(f"- `{k}` {t}{' **обяз.**' if k in req else ''}{enum} — {desc}")
        for key in ("allOf", "oneOf", "anyOf"):
            for x in s.get(key, []):
                if n := ref_name(x):
                    lines.append(f"- {key}: схема {n}")
        return "\n".join(lines)

    for path, ops in (spec.get("paths") or {}).items():
        for method, op in ops.items():
            if method not in ("get", "post", "put", "patch", "delete") or not isinstance(op, dict):
                continue
            body = [op.get("description", "")]
            params = op.get("parameters", []) + ops.get("parameters", [])
            if params:
                body.append("Параметры:")
                for p in params:
                    p = schemas.get(ref_name(p), p) if ref_name(p) else p
                    body.append(f"- `{p.get('name')}` ({p.get('in')}){' **обяз.**' if p.get('required') else ''} — "
                                f"{(p.get('description') or '').strip()}")
            for ct, media in (op.get("requestBody", {}).get("content") or {}).items():
                body.append(f"Тело запроса ({ct}):\n{props(media.get('schema', {}))}")
            for code, resp in (op.get("responses") or {}).items():
                sch = next(iter((resp.get("content") or {}).values()), {}).get("schema", {}) if isinstance(resp, dict) else {}
                body.append(f"Ответ {code}: {resp.get('description', '') if isinstance(resp, dict) else ''} "
                            f"{('схема ' + ref_name(sch)) if ref_name(sch) else ''}")
            title = f"{method.upper()} {path} — {op.get('summary') or op.get('operationId', '')}"
            chunks += [{"title": title, "url": url, "body": b} for b in _split("\n".join(filter(None, body)))]

    for name, s in schemas.items():
        text = "\n".join(filter(None, [s.get("description", ""), props(s, 1)]))
        if len(text) >= 20:
            chunks += [{"title": f"Схема {name}", "url": url, "body": b} for b in _split(text)]
    return chunks


async def load_pdf(src: dict) -> list[dict]:
    async with _client() as c:
        data = (await fetch(c, src["url"])).content
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"вместо PDF пришло {data[:15]!r} - сайт закрыт антиботом или файл переехал")
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    # нумерованные заголовки «3.2 Регистрация чека» превращаем в markdown
    md = re.sub(r"^(\d+(?:\.\d+){0,2})\.?\s+([А-ЯЁA-Z][^\n]{3,90})$",
                lambda m: "#" * min(3, m[1].count(".") + 1) + f" {m[1]} {m[2]}", text, flags=re.M)
    return chunk_markdown(md, src["url"], prefix=src.get("title", ""))


async def load_github(src: dict) -> list[dict]:
    """Тарбол репозитория; mode: md | bsl (программный интерфейс модулей 1С) | vk (методы VK API)."""
    repo, branch = src["repo"], src.get("branch", "master")
    blob = f"https://github.com/{repo}/blob/{branch}/"
    chunks = []
    with tempfile.TemporaryFile() as tmp:
        async with _client() as c, c.stream("GET", f"https://codeload.github.com/{repo}/tar.gz/{branch}") as r:
            r.raise_for_status()
            async for part in r.aiter_bytes():
                tmp.write(part)
        tmp.seek(0)
        with tarfile.open(fileobj=tmp, mode="r:gz") as tar:
            for m in tar:
                rel = m.name.split("/", 1)[-1]
                if not m.isfile() or not any(fnmatch.fnmatch(rel, g) for g in src["glob"]):
                    continue
                text = tar.extractfile(m).read().decode("utf-8-sig", "replace")
                chunks += {"md": _gh_md, "bsl": _gh_bsl, "vk": _gh_vk}[src.get("mode", "md")](text, rel, blob + rel)
    return chunks


def _gh_md(text, rel, url):
    return chunk_markdown(text, url, prefix=rel)


def _gh_bsl(text, rel, url):
    """Экспортные методы из области ПрограммныйИнтерфейс: комментарий + сигнатура."""
    module = rel.split("/")[-3] if rel.endswith("Ext/Module.bsl") else Path(rel).stem
    out, depth, inside, comment = [], 0, False, []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#Область"):
            depth += 1
            if s.split(maxsplit=1)[-1] == "ПрограммныйИнтерфейс" and not inside:
                inside, start = True, depth
        elif s.startswith("#КонецОбласти"):
            if inside and depth == start:
                inside = False
            depth -= 1
        elif inside and s.startswith("//"):
            comment.append(s[2:].strip())
        elif inside and (m := re.match(r"(Функция|Процедура)\s+(\w+)\s*\((.*?)\)?\s*Экспорт", s, re.I)):
            body = f"```bsl\n{s}\n```\n" + "\n".join(comment)
            out.append({"title": f"{module}.{m[2]}() — {m[1]}", "url": url, "body": body.strip()})
            comment = []
        elif not s.startswith("//"):
            comment = []
    return out


def _gh_vk(text, rel, url):
    out = []
    for m in json.loads(text).get("methods", []):
        ps = "\n".join(f"- `{p['name']}` {p.get('type', '')}{' **обяз.**' if p.get('required') else ''} — "
                       f"{p.get('description', '')}" for p in m.get("parameters", []))
        errs = ", ".join(e.get("$ref", "").rsplit("/", 1)[-1] for e in m.get("errors", []))
        body = (f"{m.get('description', '')}\nТокен: {', '.join(m.get('access_token_type', []))}\n"
                f"Параметры:\n{ps}\nОшибки: {errs}")
        out.append({"title": m["name"], "url": f"https://dev.vk.com/method/{m['name']}", "body": body})
    return out


LOADERS = {"html": load_html, "openapi": load_openapi, "pdf": load_pdf, "github": load_github}

# ---------- запуск ----------


def load_libraries(path: Path = PKG / "sources.toml") -> list[dict]:
    return tomllib.loads(path.read_text())["library"]


def lib_meta(lib: dict) -> dict:
    return {k: lib.get(k, "") for k in ("id", "name", "description", "homepage", "license")} | {
        "aliases": lib.get("aliases", [])}


def ingest_gotchas(db, libs: list[dict]) -> None:
    for lib in libs:
        f = PKG / "gotchas" / f"{lib['id']}.md"
        if f.exists():
            chunks = chunk_markdown(f.read_text(), lib.get("homepage", ""))
            for c in chunks:  # ссылка на первоисточник граблей - из строки «Источник: URL»
                if m := re.search(r"Источник:\s*(\S+)", c["body"]):
                    c["url"] = m[1]
                    c["body"] = c["body"].replace(m[0], "").strip()  # ссылку и так печатает get_docs
            print(f"  грабли {lib['id']}: {store.replace_library(db, lib_meta(lib), chunks, kind='gotcha')}")


async def run(only: list[str], gotchas_only: bool = False) -> int:
    db = store.connect()
    libs = [l for l in load_libraries() if not only or l["id"] in only]
    failed = 0
    for lib in [] if gotchas_only else libs:
        try:
            chunks = []
            for src in lib.get("load", []):
                got = await LOADERS[src["type"]](src)
                print(f"  {lib['id']} <- {src['type']} {src.get('spec') or src.get('url') or src.get('sitemap') or src.get('crawl') or src.get('repo') or src.get('urls', [''])[0]}: {len(got)}")
                chunks += got
            if not lib.get("load"):
                continue  # библиотека только с граблями
            if not chunks:
                raise RuntimeError("0 чанков - старые данные оставлены")
            print(f"{lib['id']}: {store.replace_library(db, lib_meta(lib), chunks)} чанков")
        except Exception as e:  # один упавший источник не роняет сборку остальных
            failed += 1
            print(f"{lib['id']}: ОШИБКА {e!r}", file=sys.stderr)
    ingest_gotchas(db, libs)
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("only", nargs="*", help="id библиотек из sources.toml")
    ap.add_argument("--lock", help="файл-замок фоновой сборки, удаляется по окончании")
    ap.add_argument("--gotchas-only", action="store_true", help="перезалить только gotchas/*.md")
    a = ap.parse_args()
    try:
        failed = asyncio.run(run(a.only, a.gotchas_only))
    finally:
        if a.lock:
            Path(a.lock).unlink(missing_ok=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
