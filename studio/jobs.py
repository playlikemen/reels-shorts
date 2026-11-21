"""Background job queue: the existing CLIs (make.py, gen_reels.py, scheduler, sync, earshot) run as subprocesses.

Two workers by default. Every job has a log file (studio-jobs/<id>.log) that the UI tails over SSE. A job can be
cancelled (its whole process group gets SIGTERM, then SIGKILL). Jobs left 'running' by a server restart are marked
'interrupted'.
"""
import asyncio, contextlib, json, os, re, signal

from . import ROOT, PY, JOB_LOGS, EARSHOT, STATE, SFX_BANK
from . import store as S
import config as K

FINAL = {"done", "failed", "cancelled", "interrupted"}
ID_RE = re.compile(r"^[A-Z]{2,4}-\d{2,4}(-[A-Z]{2})?$")
TIMES_RE = re.compile(r"^\d+(\.\d+)?(,\d+(\.\d+)?){0,15}$")
SCENES_RE = re.compile(r"^\d{1,2}(,\d{1,2}){0,20}$")
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


class JobError(Exception):
    pass


def _repo_file(rel, under, suffix=".json"):
    p = (ROOT / str(rel)).resolve()
    base = (ROOT / under).resolve()
    if base not in p.parents or p.suffix != suffix or not p.exists():
        raise JobError(f"{rel}: not an existing {suffix} file under {under}/")
    return str(p.relative_to(ROOT))


def _lang(v):
    v = (v or "").strip().lower()
    if v and not re.match(r"^[a-z]{2}$", v):
        raise JobError("lang must be two letters")
    return ["--lang", v] if v else []


def build(kind, p):
    """(argv, title, target) for a job kind and its parameters. Everything is validated; no shell is used."""
    p = p or {}
    make = [PY, str(K.ROOT / "ops" / "make.py")]
    if kind in ("render", "rerender"):
        spec = _repo_file(p.get("spec", ""), "specs")
        mode = p.get("mode", "full")
        argv = make + [spec] + _lang(p.get("lang"))
        if mode == "stills":
            t = p.get("stills") or "0.3,7,14,21"
            if not TIMES_RE.match(t):
                raise JobError("stills: comma list of seconds")
            argv += ["--stills", t]
        elif mode == "only":
            if not SCENES_RE.match(p.get("only", "")):
                raise JobError("only: comma list of scene numbers")
            argv += ["--only", p["only"], "--no-sync"]
        elif mode == "full":
            argv += ["--no-sync"]
        else:
            raise JobError("mode is full, stills or only")
        return argv, f"{'Re-render' if kind == 'rerender' else 'Render'} {spec} ({mode})", p.get("id") or spec
    if kind == "sync":
        spec = _repo_file(p.get("spec", ""), "specs")
        return make + [spec, "--sync-only"] + _lang(p.get("lang")), f"Drive + sheet row for {spec}", p.get("id") or spec
    if kind == "generate":
        files = p.get("files") or []
        if not files:
            raise JobError("files: at least one script file")
        rels = []
        for f in files:
            try:
                rels.append(_repo_file(f, "brands/craftlayer/scripts"))
            except JobError:
                fp = (STATE / "studio-scripts" / os.path.basename(str(f))).resolve()
                if not fp.exists() or fp.suffix != ".json":
                    raise
                rels.append(str(fp))
        argv = [PY, str(K.ROOT / "ops" / "gen_reels.py")] + rels
        if not TIME_RE.match(p.get("start") or ""):     # gen_reels.py's own default is a fixed date; always pass one
            raise JobError("start (first slot) must be YYYY-MM-DD HH:MM")
        argv += ["--start", p["start"]]
        return argv, f"Generate specs from {len(rels)} script file(s)", p.get("id") or ",".join(rels)
    if kind == "pull":
        tabs = [t for t in (p.get("tabs") or []) if t in K.TAB_SHEET_IDS]
        return [PY, "-m", "studio.sync", "pull"] + [x for t in tabs for x in ("--tab", t)], "Sync from Sheet" + (f" ({', '.join(tabs)})" if tabs else ""), ",".join(tabs)
    if kind == "snapshot":
        return [PY, "-m", "studio.sync", "snapshot"], "Snapshot every tab", ""
    if kind == "dryrun":
        return [PY, str(K.ROOT / "ops" / "scheduler.py"), "--dry-run"], "Scheduler dry run (what cron would post now)", ""
    if kind == "insights":
        b = p.get("brand", "")
        if b not in [x["key"] for x in K.brands()]:
            raise JobError("unknown brand")
        return [PY, "-m", "studio.tasks", "insights", b] + (["--sheet"] if p.get("sheet") else []), f"Fetch insights for {b}", b
    if kind == "publish":
        vid, plat = p.get("id", ""), p.get("platform", "")
        if not ID_RE.match(vid) or plat not in ("instagram", "youtube"):
            raise JobError("publish needs a Video ID and platform instagram or youtube")
        argv = [PY, "-m", "studio.publish_job", vid, "--platform", plat] + (["--dry-run"] if p.get("dry_run") else [])
        return argv, f"{'Dry-run ' if p.get('dry_run') else ''}Publish {vid} to {plat}", vid
    if kind == "earshot":
        words = (p.get("words") or "").strip()
        if not 3 <= len(words) <= 200:
            raise JobError("describe the sound in 3 to 200 characters")
        out = STATE / "studio-sound" / f"{p['token']}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not EARSHOT.exists():
            raise JobError(f"earshot is not installed at {EARSHOT}")
        return [str(EARSHOT), "make", words, "-o", str(out)], f"earshot: {words[:60]}", p["token"]
    raise JobError(f"unknown job kind {kind}")


class JobQueue:
    def __init__(self, workers=2, on_done=None):
        self.workers, self.on_done = workers, on_done
        self.queue, self.procs, self.tasks = None, {}, []

    async def start(self):
        JOB_LOGS.mkdir(parents=True, exist_ok=True)
        db = S.connect()
        db.execute("UPDATE jobs SET status='interrupted', ended=? WHERE status IN ('running','queued')", (S.now(),))
        self.queue = asyncio.Queue()
        self.tasks = [asyncio.create_task(self._worker()) for _ in range(self.workers)]

    async def stop(self):
        for jid, proc in list(self.procs.items()):
            self.cancel(jid)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(proc.wait(), 6)
        await asyncio.sleep(0.05)          # let the workers record the final status
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    def submit(self, kind, params=None, who="owner", argv=None, title=None, target=None):
        if argv is None:
            argv, title, target = build(kind, params)
        db = S.connect()
        cur = db.execute("INSERT INTO jobs (kind, title, args, status, created, who, target) VALUES (?,?,?,?,?,?,?)",
                         (kind, title, json.dumps({"argv": argv, "params": params or {}}), "queued", S.now(), who, target or ""))
        jid = cur.lastrowid
        log = JOB_LOGS / f"{jid}.log"
        log.write_text("")
        db.execute("UPDATE jobs SET log=? WHERE id=?", (str(log), jid))
        S.audit(f"job {kind}", target or "", None, {"job": jid, "title": title}, who)
        self.queue.put_nowait(jid)
        return jid

    def get(self, jid):
        r = S.connect().execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["args"] = json.loads(d["args"] or "{}")
        return d

    def list(self, limit=100):
        return [dict(r) | {"args": None} for r in S.connect().execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))]

    def active(self, kind=None, target=None):
        q, a = "SELECT id FROM jobs WHERE status IN ('queued','running')", []
        if kind:
            q += " AND kind=?"; a.append(kind)
        if target:
            q += " AND target=?"; a.append(target)
        return [r["id"] for r in S.connect().execute(q, a)]

    def cancel(self, jid):
        db = S.connect()
        j = self.get(jid)
        if not j or j["status"] in FINAL:
            return False
        if j["status"] == "queued":
            db.execute("UPDATE jobs SET status='cancelled', ended=? WHERE id=?", (S.now(), jid))
            return True
        proc = self.procs.get(jid)
        if proc and proc.returncode is None:
            db.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (jid,))
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            asyncio.get_event_loop().call_later(5, self._kill, proc)
            return True
        return False

    @staticmethod
    def _kill(proc):
        if proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    async def _worker(self):
        while True:
            jid = await self.queue.get()
            try:
                await self._run(jid)
            except Exception as e:      # a broken job never stops the worker
                S.connect().execute("UPDATE jobs SET status='failed', ended=? WHERE id=?", (S.now(), jid))
                with open(JOB_LOGS / f"{jid}.log", "a") as f:
                    f.write(f"\n[studio] job crashed: {e}\n")

    async def _run(self, jid):
        db = S.connect()
        j = self.get(jid)
        if not j or j["status"] != "queued":
            return
        argv = j["args"]["argv"]
        db.execute("UPDATE jobs SET status='running', started=? WHERE id=?", (S.now(), jid))
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
        with open(j["log"], "ab", buffering=0) as log:
            log.write(f"$ {' '.join(argv)}\n".encode())
            proc = await asyncio.create_subprocess_exec(*argv, cwd=str(ROOT), stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL,
                                                        start_new_session=True, env=env)
            self.procs[jid] = proc
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                log.write(chunk)
            code = await proc.wait()
            self.procs.pop(jid, None)
            cancelled = self.get(jid)["status"] == "cancelled"
            status = "cancelled" if cancelled else ("done" if code == 0 else "failed")
            log.write(f"\n[studio] exit {code} ({status})\n".encode())
        db.execute("UPDATE jobs SET status=?, ended=?, exit_code=? WHERE id=?", (status, S.now(), code, jid))
        if self.on_done:
            try:
                self.on_done(self.get(jid))
            except Exception:
                pass


def read_log(jid, offset=0, limit=256 * 1024):
    p = JOB_LOGS / f"{int(jid)}.log"
    if not p.exists():
        return "", offset
    with open(p, "rb") as f:
        f.seek(offset)
        data = f.read(limit)
    return data.decode("utf-8", "replace"), offset + len(data)


def sfx_packs():
    packs = []
    if SFX_BANK.is_dir():
        for d in sorted(SFX_BANK.iterdir()):
            if d.is_dir():
                files = sorted(f.name for f in d.glob("*.wav"))
                kinds = sorted({re.sub(r"_\d+$", "", f[:-4]) for f in files})
                packs.append({"pack": d.name, "files": files, "kinds": kinds})
    return packs
