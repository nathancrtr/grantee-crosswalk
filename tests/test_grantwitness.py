"""The fetch sidecar records when a file's bytes were first seen, not when its URL changed."""
import json

from grantee_resolver import grantwitness


class Resp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def fetch(monkeypatch, tmp_path, content, archive):
    monkeypatch.setattr(grantwitness.requests, "get", lambda url, **kw: Resp(content))
    monkeypatch.setattr(grantwitness, "ARCHIVE", archive)
    return grantwitness.source(grantwitness.fetch("cdc", tmp_path, tag="t"))


def plant_first_seen(tmp_path, value):
    p = tmp_path / "cdc.source.json"
    p.write_text(json.dumps({**json.loads(p.read_text()), "first_seen": value}))


def test_renamed_archive_keeps_first_seen(monkeypatch, tmp_path):
    fetch(monkeypatch, tmp_path, b"a,b\n", "https://old/{tag}/{agency}.csv")
    plant_first_seen(tmp_path, "2000-01-01")
    moved = fetch(monkeypatch, tmp_path, b"a,b\n", "https://new/{tag}/{agency}.csv")
    assert moved["url"] == "https://new/t/cdc.csv" and moved["first_seen"] == "2000-01-01"


def test_new_bytes_get_a_new_first_seen(monkeypatch, tmp_path):
    fetch(monkeypatch, tmp_path, b"a,b\n", "https://old/{tag}/{agency}.csv")
    plant_first_seen(tmp_path, "2000-01-01")
    changed = fetch(monkeypatch, tmp_path, b"a,b\n1,2\n", "https://old/{tag}/{agency}.csv")
    assert changed["first_seen"] != "2000-01-01"
