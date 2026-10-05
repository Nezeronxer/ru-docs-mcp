import re

from ru_docs.ingest import PKG, load_libraries

IDS = {l["id"] for l in load_libraries()}
FILES = sorted((PKG / "gotchas").glob("*.md"))


def test_every_library_has_gotchas_and_no_orphans():
    assert {f.stem for f in FILES} == IDS


def test_every_gotcha_has_source_and_date():
    for f in FILES:
        sections = re.split(r"^## ", f.read_text(), flags=re.M)[1:]
        assert sections, f.name
        for s in sections:
            head = f"{f.name}: {s.splitlines()[0]}"
            assert re.search(r"^Источник: https://\S+$", s, re.M), head
            assert re.search(r"^Проверено: \d{4}-\d{2}-\d{2}\b", s, re.M), head
