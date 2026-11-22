"""Shared fixtures: a temporary store, config and state dir, and a fake Sheet. Nothing here touches the network:
ops/composio.py is replaced by a function that fails the test if it is ever called."""
import copy, os, pathlib, sys, tempfile

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="studio-test-"))
os.environ.setdefault("STUDIO_STATE", str(_TMP / "state"))
os.environ.setdefault("STUDIO_CONFIG", str(_TMP / "config"))
os.environ.setdefault("STUDIO_DB", str(_TMP / "state" / "studio.db"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pytest

import studio  # noqa: E402  (puts ops/ on sys.path)
import composio, config as K, scheduler, sheet  # noqa: E402
from studio import store as S, sync as Y, jobs as J, auth as A  # noqa: E402


def row(vid, **kw):
    r = {h: "" for h in K.HEADERS}
    r.update({"Video ID": vid, "Category / Topic": f"topic {vid}", "Instagram Status": "Ready", "YouTube Status": "No channel",
              "Scheduled Time (IST)": "2026-12-01 19:30", "Instagram Viral Caption": "caption", "Local Path": f"out/craftlayer/{vid}/{vid.lower()}.mp4"})
    r.update(kw)
    return r


class FakeSheet:
    def __init__(self):
        self.tabs = {b["sheet_tab"]: [] for b in K.brands()}
        self.writes, self.fail_write, self.fail_read = [], False, False

    def rows(self, tab):
        if self.fail_read:
            raise RuntimeError("sheet read down")
        return [dict(copy.deepcopy(r), _row=i + 2) for i, r in enumerate(self.tabs[tab])]

    def set_cells(self, tab, n, updates):
        if self.fail_write:
            raise RuntimeError("sheet write down")
        for k, v in updates.items():
            self.tabs[tab][n - 2][k] = str(v)
            self.writes.append((tab, n, k, str(v)))

    def write_row(self, tab, n, rec):
        if self.fail_write:
            raise RuntimeError("sheet write down")
        rows = self.tabs[tab]
        vals = {h: str(rec.get(h, "")) for h in K.HEADERS}
        if n - 2 < len(rows):
            rows[n - 2] = vals
        else:
            assert n - 2 == len(rows), "mirror skipped a row"
            rows.append(vals)
        self.writes.append((tab, n, "row", vals["Video ID"]))

    def video_id_at(self, tab, n):
        if self.fail_read:
            raise RuntimeError("sheet read down")
        rows = self.tabs[tab]
        return rows[n - 2]["Video ID"] if 0 <= n - 2 < len(rows) else ""

    def upsert(self, tab, rec):
        if self.fail_write:
            raise RuntimeError("sheet write down")
        self.tabs[tab].append({h: str(rec.get(h, "")) for h in K.HEADERS})
        self.writes.append((tab, "upsert", rec["Video ID"]))


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("a test tried to call Composio")
    monkeypatch.setattr(composio, "_call", no_network)
    monkeypatch.setattr(composio, "execute", no_network)
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(K, "STATE", state)
    monkeypatch.setattr(scheduler, "LOG", state / "publish-log.jsonl")
    monkeypatch.setattr(scheduler, "CANARY", state / "youtube_canary.json")
    monkeypatch.setattr(Y, "LOG", state / "publish-log.jsonl")
    monkeypatch.setattr(Y, "BACKUP_DIR", tmp_path / "backup")
    monkeypatch.setattr(S, "DB_PATH", tmp_path / "studio.db")
    monkeypatch.setattr(J, "JOB_LOGS", tmp_path / "jobs")
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path / "config")
    S.reset_connections()
    yield tmp_path
    S.reset_connections()


@pytest.fixture
def fake(monkeypatch):
    f = FakeSheet()
    monkeypatch.setattr(sheet, "rows", f.rows)
    monkeypatch.setattr(sheet, "set_cells", f.set_cells)
    monkeypatch.setattr(sheet, "upsert", f.upsert)
    monkeypatch.setattr(sheet, "write_row", f.write_row)
    monkeypatch.setattr(sheet, "video_id_at", f.video_id_at)
    # mirror at once (the web app does it in a background thread) so tests can look at the fake Sheet
    monkeypatch.setattr(Y, "MIRROR_HOOK", lambda vid: Y.push_one(vid))
    return f


def seed():
    """Load the fake Sheet into the store once (what the one-time migration does)."""
    S.reset_connections()
    return Y.import_apply(everything=True, who="test")
