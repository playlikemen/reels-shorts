"""Reels Studio web app: routes, auth guard, static UI, media streaming, SSE job logs.

Every page has a JSON API under /api (see studio/README.md). The UI and agents use the same routes.
"""
import asyncio, contextlib, datetime, fcntl, json, mimetypes, os, re, secrets, shutil, subprocess, time
from urllib.parse import urlparse

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from sse_starlette import EventSourceResponse

from . import ROOT, WEB, FILMCRAFT, CACHE, STATE, SFX_BANK
from . import auth as A
from . import jobs as J
from . import store as S
from . import sync as Y
from . import tasks as T
import config as K
import scheduler

mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC = ("/login", "/api/login", "/static/", "/healthz", "/favicon.svg")
CSP = ("default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self'; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
ID_RE = J.ID_RE


class ApiError(Exception):
    def __init__(self, msg, status=400, **data):
        super().__init__(msg)
        self.status, self.data = status, data


def err(msg, status=400, **data):
    return JSONResponse({"error": msg, **data}, status_code=status)


def client_ip(req):
    return req.headers.get("cf-connecting-ip") or (req.client.host if req.client else "")


def is_https(req):
    return (req.url.scheme == "https" or req.headers.get("x-forwarded-proto", "").lower() == "https"
            or '"https"' in req.headers.get("cf-visitor", ""))


# ---------- auth guard (pure ASGI, so SSE and file streaming are untouched) ----------

class Guard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        req = Request(scope)
        path, method = scope["path"], scope["method"]
        st = STATE_REF
        user, via = None, None
        authz = req.headers.get("authorization", "")
        if authz.lower().startswith("bearer "):
            name = A.check_token(st.auth, authz[7:].strip())
            if name:
                user, via = f"token:{name}", "token"
        if not user:
            sess = A.read_session(st.auth["secret"], req.cookies.get(A.COOKIE))
            if sess:
                user, via = sess["u"], "cookie"
                scope.setdefault("state", {})["session"] = sess
        scope.setdefault("state", {})["user"] = user
        scope["state"]["via"] = via
        public = path in ("/login", "/api/login", "/healthz", "/favicon.svg") or path.startswith("/static/")
        if not public and not user:
            resp = err("login required", 401) if path.startswith("/api/") else RedirectResponse("/login", 303)
            return await resp(scope, receive, send)
        if method in UNSAFE and via == "cookie":
            if not A.check_csrf(st.auth["secret"], scope["state"]["session"], req.headers.get("x-csrf-token", "")):
                return await err("missing or bad CSRF token (send X-CSRF-Token from /api/session)", 403)(scope, receive, send)
        editor = path.startswith("/editor")

        async def send_wrapped(msg):
            if msg["type"] == "http.response.start":
                h = msg.setdefault("headers", [])
                h += [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"same-origin")]
                if editor:
                    h += [(b"cross-origin-opener-policy", b"same-origin"), (b"cross-origin-embedder-policy", b"require-corp"),
                          (b"cross-origin-resource-policy", b"same-origin")]
                else:
                    h += [(b"x-frame-options", b"DENY"), (b"content-security-policy", CSP.encode())]
                if path.startswith("/api/"):
                    h.append((b"cache-control", b"no-store"))
            await send(msg)

        await self.app(scope, receive, send_wrapped)


class _State:
    auth = None
    limiter = A.RateLimit()
    queue = None
    conn_cache = None


STATE_REF = _State()


def who(req):
    return req.scope.get("state", {}).get("user") or "?"


async def body(req):
    try:
        data = await req.json()
    except Exception:
        raise ApiError("send a JSON body")
    if not isinstance(data, dict):
        raise ApiError("send a JSON object")
    return data


def route(fn):
    """Turn ApiError / SyncError / JobError into JSON errors."""
    async def wrapper(req):
        try:
            return await fn(req)
        except (ApiError, Y.SyncError) as e:
            return err(str(e), e.status, **e.data)
        except J.JobError as e:
            return err(str(e), 400)
    wrapper.__name__ = fn.__name__
    return wrapper


# ---------- pages and login ----------

async def index(req):
    return FileResponse(WEB / "index.html", headers={"cache-control": "no-cache"})


async def login_page(req):
    if req.scope["state"].get("user"):
        return RedirectResponse("/", 303)
    return FileResponse(WEB / "login.html", headers={"cache-control": "no-cache"})


async def favicon(req):
    return FileResponse(WEB / "favicon.svg", media_type="image/svg+xml")


async def healthz(req):
    return Response("ok", media_type="text/plain")


@route
async def api_login(req):
    ip = client_ip(req)
    origin = req.headers.get("origin")
    if origin and urlparse(origin).netloc != req.headers.get("host", ""):
        return err("cross-site login refused", 403)
    st = STATE_REF
    if st.limiter.blocked(ip):
        return err("too many failed logins; wait 15 minutes", 429, retry_after=900)
    data = await body(req)
    ok = await run_in_threadpool(A.check_password, str(data.get("password", "")), st.auth["password"])
    if not ok:
        st.limiter.fail(ip)
        S.audit("login failed", "", None, None, "?", ip)
        await asyncio.sleep(0.4)
        return err("wrong password", 401)
    st.limiter.ok(ip)
    cookie = A.make_session(st.auth["secret"])
    sess = A.read_session(st.auth["secret"], cookie)
    resp = JSONResponse({"ok": True, "csrf": A.csrf_token(st.auth["secret"], sess)})
    resp.set_cookie(A.COOKIE, cookie, max_age=A.SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=is_https(req), path="/")
    S.audit("login", "", None, {"https": is_https(req)}, sess["u"], ip)
    return resp


async def api_logout(req):
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(A.COOKIE, path="/")
    return resp


async def api_session(req):
    sess = req.scope["state"].get("session")
    return JSONResponse({"user": who(req), "csrf": A.csrf_token(STATE_REF.auth["secret"], sess) if sess else None,
                         "has_initial_password_file": (A._paths()[1]).exists()})


# ---------- brands and reels ----------

def brand_info():
    out = []
    for b in K.brands():
        packs = {s: v.get("sfx_pack", "") for s, v in b.get("styles", {}).items()}
        out.append({"key": b["key"], "name": b["name"], "prefix": b["id_prefix"], "tab": b["sheet_tab"],
                    "instagram": b["instagram"]["handle"], "youtube": (b.get("youtube") or {}).get("handle", ""),
                    "cap": b.get("max_reels_per_day"), "slots": b.get("slots_ist", []), "sfx_packs": packs,
                    "insights_tab": b.get("insights_tab", ""), "posted_today": scheduler.posted_today(b["id_prefix"])})
    return out


async def api_brands(req):
    return JSONResponse({"brands": await run_in_threadpool(brand_info)})


async def api_reels(req):
    q = req.query_params
    reels = S.list_reels()
    if q.get("brand"):
        reels = [r for r in reels if r["brand"] == q["brand"]]
    if q.get("status"):
        s = q["status"].lower()
        reels = [r for r in reels if r["Instagram Status"].lower().startswith(s) or r["YouTube Status"].lower().startswith(s)]
    if q.get("q"):
        words = q["q"].lower().split()
        reels = [r for r in reels if all(w in json.dumps({h: r[h] for h in K.HEADERS}, ensure_ascii=False).lower() for w in words)]
    return JSONResponse({"reels": reels, "count": len(reels), "last_pull": S.get_setting("last_pull"),
                         "unsynced": await run_in_threadpool(Y.unsynced_renders)})


@route
async def api_reel(req):
    vid = req.path_params["vid"]
    r = S.get_reel(vid)
    if not r:
        raise ApiError(f"no reel {vid}", 404)
    db = S.connect()
    log = [json.loads(x["data"]) for x in db.execute("SELECT data FROM publish_log WHERE video=? ORDER BY at", (vid,))]
    ins = [dict(x) for x in db.execute("SELECT * FROM insights WHERE video_id=? OR (permalink<>'' AND permalink=?) ORDER BY fetched_at",
                                       (vid, r["Instagram Post URL"]))]
    d = Y.out_dir(r["brand"], vid, r["Local Path"])
    files = sorted(p.name for p in d.iterdir() if p.suffix in (".mp4", ".jpg", ".srt") and not p.name.startswith("still_")) if d.is_dir() else []
    stills = sorted(p.name for p in d.glob("still_*.jpg")) if d.is_dir() else []
    spec = {}
    if r["spec_path"] and (ROOT / r["spec_path"]).exists():
        try:
            raw = json.loads((ROOT / r["spec_path"]).read_text())
            spec = {"style": raw.get("style"), "title": raw.get("title"), "sources": (raw.get("meta") or {}).get("sources", []),
                    "langs": list((raw.get("langs") or {}).keys()), "scenes": len(raw.get("scenes", []))}
        except ValueError:
            pass
    out_rel = str(d.relative_to(ROOT)) if d.is_dir() else ""
    return JSONResponse({"reel": r, "publish_log": log, "insights": ins, "files": files, "stills": stills, "out_dir": out_rel,
                         "spec": spec, "snapshots": Y.list_snapshots()[:30],
                         "keyword": T.cta_keyword(r["Instagram Viral Caption"])})


@route
async def api_edit(req):
    vid = req.path_params["vid"]
    data = await body(req)
    fields = data.get("fields") or {}
    if not isinstance(fields, dict) or not fields:
        raise ApiError("fields: {header: value}")
    if "Scheduled Time (IST)" in fields and "Date" not in fields and fields["Scheduled Time (IST)"]:
        fields["Date"] = str(fields["Scheduled Time (IST)"])[:10]
    res = await run_in_threadpool(Y.edit, vid, fields, data.get("base"), bool(data.get("force")), who(req), client_ip(req),
                                  bool(data.get("allow_repost")))
    code = {"ok": 200, "unchanged": 200, "pending": 202, "conflict": 409}[res["status"]]
    return JSONResponse(res, status_code=code)


def hold_fields(reel, hold):
    f = {}
    for c in Y.STATUS_COLS:
        if hold and reel[c] == "Ready":
            f[c] = "Hold"
        elif not hold and reel[c] == "Hold":
            f[c] = "Ready"
    return f


@route
async def api_hold(req):
    vid = req.path_params["vid"]
    data = await body(req)
    r = S.get_reel(vid)
    if not r:
        raise ApiError(f"no reel {vid}", 404)
    f = hold_fields(r, bool(data.get("hold", True)))
    if not f:
        raise ApiError("nothing to change: hold works on Ready rows, unhold on Hold rows", 409)
    res = await run_in_threadpool(Y.edit, vid, f, None, False, who(req), client_ip(req))
    return JSONResponse(res, status_code={"ok": 200, "unchanged": 200, "pending": 202, "conflict": 409}[res["status"]])


@route
async def api_drop_pending(req):
    data = await body(req)
    return JSONResponse({"reel": Y.drop_pending(req.path_params["vid"], data.get("field", ""), who(req), client_ip(req))})


@route
async def api_bulk(req):
    data = await body(req)
    ids = [i for i in data.get("ids") or [] if isinstance(i, str) and ID_RE.match(i)]
    if not ids or data.get("action") not in ("hold", "ready", "schedule"):
        raise ApiError("ids and action (hold, ready, schedule)")
    if data["action"] == "schedule" and not Y.TIME_RE.match(data.get("start", "")):
        raise ApiError("start must be YYYY-MM-DD HH:MM")
    params = {"ids": ids, "action": data["action"], "start": data.get("start", ""), "every_days": int(data.get("every_days") or 1)}
    jid = STATE_REF.queue.submit("bulk", params, who(req), argv=[J.PY, "-m", "studio.sync", "bulk", json.dumps(params), "--who", who(req)],
                                 title=f"Bulk {data['action']} {len(ids)} reels", target=",".join(ids)[:200])
    return JSONResponse({"job": jid}, status_code=202)


@route
async def api_restore(req):
    vid = req.path_params["vid"]
    if req.method == "GET":
        res = await run_in_threadpool(Y.restore_row, vid, req.query_params.get("date", ""), True)
        return JSONResponse(res)
    data = await body(req)
    res = await run_in_threadpool(Y.restore_row, vid, data.get("date", ""), data.get("dry_run", True) is not False, who(req), client_ip(req))
    return JSONResponse(res)


async def api_snapshots(req):
    return JSONResponse({"snapshots": Y.list_snapshots(), "last": S.get_setting("last_snapshot")})


async def api_unsynced(req):
    return JSONResponse({"unsynced": await run_in_threadpool(Y.unsynced_renders)})


@route
async def api_sync(req):
    data = await body(req)
    jid = STATE_REF.queue.submit("pull", {"tabs": data.get("tabs") or []}, who(req))
    return JSONResponse({"job": jid}, status_code=202)


# ---------- publish ----------

def lock_busy():
    try:
        with open(K.STATE / "scheduler.lock", "a") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        return False
    return False


def publish_checks(vid, platform):
    r = S.get_reel(vid)
    if not r:
        raise ApiError(f"no reel {vid}", 404)
    b = K.brand(r["brand"])
    col = "Instagram Status" if platform == "instagram" else "YouTube Status"
    acc = b.get(platform) if platform in ("instagram", "youtube") else None
    if not acc:
        raise ApiError(f"{b['name']} has no {platform} channel connected", 400)
    cap = b.get("max_reels_per_day") if platform == "instagram" else None
    sent = scheduler.posted_today(b["id_prefix"]) if platform == "instagram" else None
    mp4 = ROOT / r["Local Path"] if r["Local Path"] else None
    caption = (r["Instagram Viral Caption"].rstrip() + "\n\n" + r["Instagram Hashtags"]) if platform == "instagram" else r["YouTube Best SEO Description"]
    problems = []
    if r[col] != "Ready":
        problems.append(f"{col} is '{r[col]}'; only Ready rows are posted. Set it to Ready first.")
    if r["pending"]:
        problems.append("this row has edits waiting to reach the Sheet; sync first")
    if r["missing"]:
        problems.append("this row is missing from the Sheet")
    if not mp4 or not mp4.exists():
        problems.append("the local MP4 is missing")
    elif mp4.stat().st_size < K.MIN_MP4_BYTES:
        problems.append("the MP4 is under 100 KB")
    canary = scheduler.canary_state()
    if platform == "youtube" and canary.get("state") in ("pending", "blocked"):
        problems.append(f"YouTube canary is {canary['state']}; the scheduler will not upload until it passes")
    if STATE_REF.queue and STATE_REF.queue.active("publish", vid):
        problems.append("a publish job for this reel is already queued or running")
    return {"reel": r, "brand": b["name"], "handle": acc["handle"], "platform": platform, "status": r[col],
            "caption": caption, "title": r["YouTube Title"] if platform == "youtube" else "",
            "cap": cap, "posted_today": sent, "over_cap": bool(cap and sent >= cap), "lock_busy": lock_busy(),
            "problems": problems, "canary": canary.get("state")}


@route
async def api_publish_preview(req):
    q = req.query_params
    p = await run_in_threadpool(publish_checks, q.get("id", ""), q.get("platform", "instagram"))
    p.pop("reel")
    return JSONResponse(p)


@route
async def api_publish(req):
    data = await body(req)
    vid, platform = str(data.get("id", "")), data.get("platform", "")
    if not ID_RE.match(vid) or platform not in ("instagram", "youtube"):
        raise ApiError("id and platform (instagram or youtube)")
    dry = bool(data.get("dry_run"))
    if not dry and data.get("confirm") is not True:
        raise ApiError("publishing needs confirm: true (one confirm per reel)")
    p = await run_in_threadpool(publish_checks, vid, platform)
    if p["problems"]:
        raise ApiError(p["problems"][0], 409, problems=p["problems"])
    if p["over_cap"] and not dry and data.get("override_cap") is not True:
        raise ApiError(f"{p['brand']} already posted {p['posted_today']} of {p['cap']} today; tick the override to post anyway",
                       409, need_override=True)
    if p["lock_busy"]:
        raise ApiError("the scheduler is running right now; try again in a minute", 409, lock_busy=True)
    jid = STATE_REF.queue.submit("publish", {"id": vid, "platform": platform, "dry_run": dry}, who(req))
    S.audit("publish requested" if not dry else "publish dry-run", vid, None,
            {"platform": platform, "job": jid, "override_cap": bool(data.get("override_cap"))}, who(req), client_ip(req))
    return JSONResponse({"job": jid}, status_code=202)


# ---------- jobs ----------

async def api_jobs(req):
    return JSONResponse({"jobs": STATE_REF.queue.list(int(req.query_params.get("limit", 100)))})


@route
async def api_job_new(req):
    data = await body(req)
    kind = data.get("kind", "")
    if kind in ("publish", "bulk"):
        raise ApiError(f"use /api/{'publish' if kind == 'publish' else 'reels/bulk'} for that")
    jid = STATE_REF.queue.submit(kind, data.get("params") or {}, who(req))
    return JSONResponse({"job": jid}, status_code=202)


@route
async def api_job(req):
    j = STATE_REF.queue.get(int(req.path_params["jid"]))
    if not j:
        raise ApiError("no such job", 404)
    text, _ = J.read_log(j["id"], max(0, os.path.getsize(j["log"]) - 200_000) if j["log"] and os.path.exists(j["log"]) else 0)
    j["log_tail"] = text
    return JSONResponse(j)


@route
async def api_job_cancel(req):
    ok = STATE_REF.queue.cancel(int(req.path_params["jid"]))
    S.audit("job cancel", str(req.path_params["jid"]), None, {"ok": ok}, who(req), client_ip(req))
    return JSONResponse({"cancelled": ok})


async def api_job_stream(req):
    jid = int(req.path_params["jid"])
    q = STATE_REF.queue

    async def gen():
        off = 0
        while True:
            if await req.is_disconnected():
                return
            text, off = J.read_log(jid, off)
            if text:
                yield {"event": "log", "data": json.dumps(text)}
                continue
            j = q.get(jid)
            if not j or j["status"] in J.FINAL:
                yield {"event": "end", "data": json.dumps({"status": j["status"] if j else "gone", "exit_code": j and j["exit_code"]})}
                return
            await asyncio.sleep(0.5)

    return EventSourceResponse(gen(), ping=15)


def on_job_done(j):
    """After a job that changed the Sheet, pull that tab so the studio shows the new state."""
    if j["kind"] not in ("publish", "sync", "bulk") or j["status"] == "cancelled":
        return
    tabs = set()
    for b in K.brands():
        if j["kind"] == "publish" and j["target"].startswith(b["id_prefix"] + "-"):
            tabs.add(b["sheet_tab"])
        if j["kind"] == "sync" and f"specs/{b['key']}/" in j["title"]:
            tabs.add(b["sheet_tab"])
        if j["kind"] == "bulk" and any(t.startswith(b["id_prefix"] + "-") for t in j["target"].split(",")):
            tabs.add(b["sheet_tab"])
    if tabs:
        STATE_REF.queue.submit("pull", {"tabs": sorted(tabs)}, "studio")


# ---------- scripts (CraftLayer) ----------

SCRIPTS = ROOT / "brands" / "craftlayer" / "scripts"
SCRIPT_ID = re.compile(r"^CR-\d{3}$")


async def api_scripts(req):
    out = []
    for f in sorted(SCRIPTS.glob("*.json")):
        try:
            for r in json.loads(f.read_text()):
                out.append({"file": str(f.relative_to(ROOT)), "id": r.get("id"), "topic": r.get("topic"), "script": r})
        except ValueError:
            pass
    return JSONResponse({"scripts": out, "schema": (ROOT / "brands" / "craftlayer" / "reel_schema.md").read_text()})


def check_script(s):
    import gen_reels
    out = {"errors": [], "words": 0, "parts": []}
    try:
        errs, tot = gen_reels.check(s)
        out["errors"], out["words"] = errs, tot
        parts = [("hook", s["hook"]["say"])] + [(f"problem {i + 1}", p["say"]) for i, p in enumerate(s["problems"])] + \
                [(f"fix {i + 1}", p["fix"]["say"]) for i, p in enumerate(s["problems"])] + [("recap", s["recap_say"]), ("cta", s["cta_say"])]
        out["parts"] = [{"part": k, "words": gen_reels.words(v), "over": gen_reels.words(v) > 20} for k, v in parts]
        out["errors"] += [f"{p['part']}: {p['words']} words (max 20)" for p in out["parts"] if p["over"]]
        kw = s.get("keyword", "")
        if not re.match(r"^[A-Z]{2,8}$", kw):
            out["errors"].append("keyword: one upper-case word, at most 8 letters")
        cap = s.get("caption", "")
        if "AI-generated" not in cap:
            out["warnings"] = ["caption gets 'Voiceover is AI-generated.' appended"]
        tags = s.get("hashtags") or []
        if not 5 <= len(tags) <= 8 or (tags and tags[-1] != "#craftlayer"):
            out["errors"].append("hashtags: 5 to 8, last one #craftlayer")
        gen_reels.spec_for(s, 0, "2026-01-01 19:30")
    except (KeyError, TypeError, IndexError) as e:
        out["errors"].append(f"missing or malformed field: {e}")
    return out


@route
async def api_script_check(req):
    data = await body(req)
    return JSONResponse(check_script(data.get("script") or {}))


@route
async def api_script_save(req):
    data = await body(req)
    s = data.get("script") or {}
    if not SCRIPT_ID.match(str(s.get("id", ""))):
        raise ApiError("id must look like CR-135")
    chk = check_script(s)
    if chk["errors"] and not data.get("force"):
        raise ApiError("fix the script first: " + "; ".join(chk["errors"][:4]), 422, check=chk)
    d = STATE / "studio-scripts"
    d.mkdir(parents=True, exist_ok=True)
    single = d / f"{s['id']}.json"
    single.write_text(json.dumps([s], indent=1, ensure_ascii=False) + "\n")
    book = SCRIPTS / "studio.json"
    entries = json.loads(book.read_text()) if book.exists() else []
    entries = [e for e in entries if e.get("id") != s["id"]] + [s]
    book.write_text(json.dumps(sorted(entries, key=lambda e: e["id"]), indent=1, ensure_ascii=False) + "\n")
    S.audit("script saved", s["id"], None, {"file": str(book.relative_to(ROOT))}, who(req), client_ip(req))
    return JSONResponse({"file": single.name, "book": str(book.relative_to(ROOT)), "spec": f"specs/craftlayer/{s['id']}.json"})


# ---------- insights, comments, health ----------

async def api_insights(req):
    rows = T.latest_insights()
    b = req.query_params.get("brand")
    if b:
        rows = [r for r in rows if r["brand"] == b]
    weeks = {}
    for r in rows:
        try:
            y, w, _ = datetime.date.fromisoformat(r["posted"]).isocalendar()
        except ValueError:
            continue
        k = f"{y}-W{w:02d}"
        e = weeks.setdefault(k, {"week": k, "views": 0, "shares": 0, "reels": 0})
        e["views"] += r["views"] or 0; e["shares"] += r["shares"] or 0; e["reels"] += 1
    by = sorted(rows, key=lambda r: -(r["views"] or 0))
    fetched = {x["key"]: S.get_setting(f"insights_at:{x['key']}") for x in K.brands()}
    return JSONResponse({"rows": rows, "top": by[:5], "bottom": by[-5:][::-1] if len(by) > 5 else [], "weeks": sorted(weeks.values(), key=lambda e: e["week"]),
                         "fetched": fetched})


@route
async def api_insights_fetch(req):
    data = await body(req)
    jid = STATE_REF.queue.submit("insights", {"brand": data.get("brand", ""), "sheet": bool(data.get("sheet"))}, who(req))
    return JSONResponse({"job": jid}, status_code=202)


def _brand_key(k):
    if k not in [b["key"] for b in K.brands()]:
        raise ApiError("unknown brand")
    return k


async def api_comments(req):
    k = req.query_params.get("brand", "")
    try:
        _brand_key(k)
    except ApiError as e:
        return err(str(e))
    return JSONResponse(T.cached_comments(k) or {"brand": k, "media": [], "fetched_at": None})


@route
async def api_comments_refresh(req):
    data = await body(req)
    k = _brand_key(data.get("brand", ""))
    try:
        res = await run_in_threadpool(T.fetch_comments, k)
    except Exception as e:
        raise ApiError(f"could not read comments through Composio: {str(e)[:300]}", 502)
    return JSONResponse(res)


@route
async def api_comments_reply(req):
    data = await body(req)
    k = _brand_key(data.get("brand", ""))
    if data.get("send") is not True:
        raise ApiError("replies go out only on an explicit Send (send: true)")
    msg = str(data.get("message", ""))
    e = T.check_reply(msg)
    if e:
        raise ApiError(e)
    try:
        res = await run_in_threadpool(T.reply_comment, k, str(data.get("comment_id", "")), msg)
    except Exception as ex:
        s = str(ex)
        hint = "the Composio reply tool is not available for this account" if "not found" in s.lower() or "unknown tool" in s.lower() else ""
        S.audit("comment reply failed", str(data.get("comment_id")), None, {"brand": k, "message": msg, "error": s[:200]}, who(req), client_ip(req))
        raise ApiError(hint or f"reply failed: {s[:300]}", 502)
    S.audit("comment reply", str(data.get("comment_id")), None, {"brand": k, "message": msg, "result": res}, who(req), client_ip(req))
    return JSONResponse({"ok": True, "result": res})


async def api_health(req):
    local = await run_in_threadpool(T.health_local)
    local["jobs_running"] = len(STATE_REF.queue.active())
    local["filmcraft"] = (FILMCRAFT / "index.html").exists()
    local["earshot"] = J.EARSHOT.exists()
    return JSONResponse(local)


async def api_health_connections(req):
    c = STATE_REF.conn_cache
    if c and time.time() - c[0] < 600 and req.query_params.get("fresh") != "1":
        return JSONResponse({**c[1], "cached_at": c[0]})
    res = await run_in_threadpool(T.health_connections)
    STATE_REF.conn_cache = (time.time(), res)
    return JSONResponse({**res, "cached_at": time.time()})


# ---------- sound ----------

async def api_sound(req):
    return JSONResponse({"packs": J.sfx_packs(), "brands": brand_info_sound(), "earshot": J.EARSHOT.exists()})


def brand_info_sound():
    return [{"key": b["key"], "name": b["name"], "styles": {s: v.get("sfx_pack", "") for s, v in b.get("styles", {}).items()}} for b in K.brands()]


async def sound_file(req):
    pack, name = req.path_params["pack"], req.path_params["name"]
    if pack == "_tmp":
        p = STATE / "studio-sound" / name
    else:
        p = SFX_BANK / pack / name
    if not re.match(r"^[\w.-]+\.wav$", name) or not re.match(r"^[\w-]+$", pack) or not p.is_file():
        return err("no such sound", 404)
    return FileResponse(p, media_type="audio/wav")


@route
async def api_sound_make(req):
    data = await body(req)
    token = secrets.token_hex(8)
    jid = STATE_REF.queue.submit("earshot", {"words": data.get("words", ""), "token": token}, who(req))
    return JSONResponse({"job": jid, "token": token, "url": f"/sound/_tmp/{token}.wav"}, status_code=202)


@route
async def api_sound_use(req):
    data = await body(req)
    token, pack, name = str(data.get("token", "")), str(data.get("pack", "")), str(data.get("name", ""))
    src = STATE / "studio-sound" / f"{token}.wav"
    if not re.match(r"^[0-9a-f]{16}$", token) or not src.exists():
        raise ApiError("make the sound first", 404)
    if not re.match(r"^[a-z]+_\d+\.wav$", name) or not (SFX_BANK / pack).is_dir() or not re.match(r"^[\w-]+$", pack):
        raise ApiError("pick an existing pack and a name like whoosh_2.wav")
    dst = SFX_BANK / pack / name
    if dst.exists():
        bk = STATE / "studio-sound" / "replaced"
        bk.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, bk / f"{pack}-{name[:-4]}-{int(time.time())}.wav")
    shutil.copy2(src, dst)
    S.audit("sfx replaced", f"{pack}/{name}", None, {"from": token}, who(req), client_ip(req))
    return JSONResponse({"ok": True, "file": str(dst.relative_to(ROOT))})


@route
async def api_sound_brand(req):
    data = await body(req)
    k, style, pack = _brand_key(data.get("brand", "")), str(data.get("style", "")), str(data.get("pack", ""))
    packs = [p["pack"] for p in J.sfx_packs()]
    if pack and pack not in packs:
        raise ApiError("unknown pack")
    path = ROOT / "brands" / k / "brand.json"
    b = json.loads(path.read_text())
    if style not in b.get("styles", {}):
        raise ApiError("unknown style for this brand")
    before = b["styles"][style].get("sfx_pack", "")
    if pack:
        b["styles"][style]["sfx_pack"] = pack
    else:
        b["styles"][style].pop("sfx_pack", None)
    path.write_text(json.dumps(b, indent=2, ensure_ascii=False) + "\n")
    S.audit("sfx pack", f"{k}/{style}", {"sfx_pack": before}, {"sfx_pack": pack}, who(req), client_ip(req))
    return JSONResponse({"ok": True})


# ---------- audit and settings ----------

async def api_audit(req):
    lim = min(1000, int(req.query_params.get("limit", 200)))
    rows = [dict(r) for r in S.connect().execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (lim,))]
    return JSONResponse({"audit": rows})


@route
async def api_password(req):
    data = await body(req)
    st = STATE_REF
    if not await run_in_threadpool(A.check_password, str(data.get("current", "")), st.auth["password"]):
        raise ApiError("current password is wrong", 403)
    try:
        st.auth = await run_in_threadpool(A.set_password, str(data.get("new", "")))
    except ValueError as e:
        raise ApiError(str(e))
    S.audit("password changed", "", None, None, who(req), client_ip(req))
    return JSONResponse({"ok": True, "relogin": True})


async def api_tokens(req):
    return JSONResponse({"tokens": [{"name": n, "created": t["created"]} for n, t in (STATE_REF.auth.get("tokens") or {}).items()]})


@route
async def api_token_new(req):
    data = await body(req)
    name = str(data.get("name", ""))
    if not re.match(r"^[\w-]{2,32}$", name):
        raise ApiError("name: 2 to 32 letters, digits, - or _")
    tok = A.create_token(name)
    STATE_REF.auth = A.load()
    S.audit("api token created", name, None, None, who(req), client_ip(req))
    return JSONResponse({"name": name, "token": tok})


@route
async def api_token_del(req):
    data = await body(req)
    A.revoke_token(str(data.get("name", "")))
    STATE_REF.auth = A.load()
    S.audit("api token revoked", str(data.get("name", "")), None, None, who(req), client_ip(req))
    return JSONResponse({"ok": True})


# ---------- media, thumbnails, editor ----------

MEDIA_EXT = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".srt": "text/plain; charset=utf-8"}


async def media(req):
    rel = req.path_params["path"]
    base = (ROOT / "out").resolve()
    p = (base / rel).resolve()
    if base not in p.parents or p.suffix.lower() not in MEDIA_EXT or not p.is_file():
        return err("not found", 404)
    return FileResponse(p, media_type=MEDIA_EXT[p.suffix.lower()], headers={"cache-control": "private, max-age=300"})


def make_thumb(vid):
    r = S.get_reel(vid)
    if r:
        d = Y.out_dir(r["brand"], vid, r["Local Path"])
    else:
        d = next((ROOT / "out" / b["key"] / vid for b in K.brands() if (ROOT / "out" / b["key"] / vid).is_dir()), None)
    if not d or not d.is_dir():
        return None
    src = d / "thumb.jpg"
    mp4 = d / f"{vid.lower()}.mp4"
    if not src.exists() and not mp4.exists():
        return None
    ref = src if src.exists() else mp4
    out = CACHE / "thumbs" / f"{vid}-{int(ref.stat().st_mtime)}.jpg"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + (["-i", str(src)] if src.exists() else ["-ss", "1", "-i", str(mp4), "-frames:v", "1"]) + \
          ["-vf", "scale=360:-2", "-q:v", "5", str(out)]
    try:
        subprocess.run(cmd, timeout=30, check=True, capture_output=True)
    except Exception:
        return src if src.exists() else None
    return out


async def thumb(req):
    vid = req.path_params["vid"]
    if not ID_RE.match(vid):
        return err("bad id", 404)
    p = await run_in_threadpool(make_thumb, vid)
    if not p:
        return FileResponse(WEB / "no-thumb.svg", media_type="image/svg+xml")
    return FileResponse(p, media_type="image/jpeg", headers={"cache-control": "private, max-age=86400"})


EDITOR_CACHE = {".wasm": "public, max-age=31536000, immutable", ".js": "public, max-age=31536000, immutable"}


async def editor(req):
    rel = req.path_params.get("path", "") or "index.html"
    base = FILMCRAFT.resolve()
    if not (base / "index.html").exists():
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>Editor</title><body style='font:16px system-ui;padding:24px'>"
                            f"<h1>FilmCraft is not installed</h1><p>Expected the web build at <code>{FILMCRAFT}</code>.</p>"
                            f"<p><a href='/'>Back to Reels Studio</a></p>", status_code=404)
    p = (base / rel).resolve()
    if (base not in p.parents and p != base) or not p.is_file() or p.name.startswith("_"):
        return Response("not found", 404)
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if p.suffix == ".wasm":
        ctype = "application/wasm"
    return FileResponse(p, media_type=ctype, headers={"cache-control": EDITOR_CACHE.get(p.suffix, "no-cache")})


async def editor_root(req):
    return RedirectResponse("/editor/", 307)


# ---------- app ----------

@contextlib.asynccontextmanager
async def lifespan(app):
    STATE_REF.auth = A.ensure()
    S.connect()
    STATE_REF.queue = J.JobQueue(workers=int(os.environ.get("STUDIO_WORKERS", "2")), on_done=on_job_done)
    await STATE_REF.queue.start()
    yield
    await STATE_REF.queue.stop()


def create_app():
    routes = [
        Route("/", index), Route("/login", login_page), Route("/favicon.svg", favicon), Route("/healthz", healthz),
        Route("/api/login", api_login, methods=["POST"]), Route("/api/logout", api_logout, methods=["POST"]),
        Route("/api/session", api_session), Route("/api/brands", api_brands),
        Route("/api/reels", api_reels), Route("/api/reels/bulk", api_bulk, methods=["POST"]),
        Route("/api/reels/{vid}", api_reel), Route("/api/reels/{vid}", api_edit, methods=["PATCH"]),
        Route("/api/reels/{vid}/hold", api_hold, methods=["POST"]),
        Route("/api/reels/{vid}/pending/drop", api_drop_pending, methods=["POST"]),
        Route("/api/reels/{vid}/restore", api_restore, methods=["GET", "POST"]),
        Route("/api/snapshots", api_snapshots), Route("/api/unsynced", api_unsynced),
        Route("/api/sync", api_sync, methods=["POST"]),
        Route("/api/publish/preview", api_publish_preview), Route("/api/publish", api_publish, methods=["POST"]),
        Route("/api/jobs", api_jobs), Route("/api/jobs", api_job_new, methods=["POST"]),
        Route("/api/jobs/{jid:int}", api_job), Route("/api/jobs/{jid:int}/cancel", api_job_cancel, methods=["POST"]),
        Route("/api/jobs/{jid:int}/stream", api_job_stream),
        Route("/api/scripts", api_scripts), Route("/api/scripts/check", api_script_check, methods=["POST"]),
        Route("/api/scripts/save", api_script_save, methods=["POST"]),
        Route("/api/insights", api_insights), Route("/api/insights/fetch", api_insights_fetch, methods=["POST"]),
        Route("/api/comments", api_comments), Route("/api/comments/refresh", api_comments_refresh, methods=["POST"]),
        Route("/api/comments/reply", api_comments_reply, methods=["POST"]),
        Route("/api/health", api_health), Route("/api/health/connections", api_health_connections),
        Route("/api/sound", api_sound), Route("/api/sound/make", api_sound_make, methods=["POST"]),
        Route("/api/sound/use", api_sound_use, methods=["POST"]), Route("/api/sound/brand", api_sound_brand, methods=["POST"]),
        Route("/sound/{pack}/{name}", sound_file),
        Route("/api/audit", api_audit),
        Route("/api/settings/password", api_password, methods=["POST"]),
        Route("/api/settings/tokens", api_tokens), Route("/api/settings/tokens", api_token_new, methods=["POST"]),
        Route("/api/settings/tokens/revoke", api_token_del, methods=["POST"]),
        Route("/media/{path:path}", media), Route("/thumb/{vid}.jpg", thumb),
        Route("/editor", editor_root), Route("/editor/", editor), Route("/editor/{path:path}", editor),
        Mount("/static", app=StaticFiles(directory=str(WEB)), name="static"),
    ]
    app = Starlette(routes=routes, lifespan=lifespan, max_body_size=4 * 1024 * 1024)
    return Guard(app)


app = create_app()
