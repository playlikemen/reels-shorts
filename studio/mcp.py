"""MCP server for Reels Studio: Streamable HTTP transport, JSON-RPC 2.0 over POST /mcp (protocol 2025-06-18).

- Without a key: read-only tools, with private fields removed (Drive and direct MP4 links, /media URLs, local paths,
  audit IPs, Composio account ids, job logs).
- With the key (Authorization: Bearer <key> or X-API-Key: <key>): every tool, unredacted. Calls are audited as
  who="mcp-key". Publish tools need confirm: true (dry_run: true posts nothing) and take the scheduler's shared lock.

Each tool runs the same code as the matching /api route (same checks, same audit), through a request built here.
"""
import json, os, re, secrets, shutil, urllib.parse, urllib.request

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import STATE
from . import store as S
from . import sync as Y
import config as K

PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
SERVER = {"name": "reels-studio", "title": "Reels Studio", "version": "1.0"}
INSTRUCTIONS = ("Reels Studio runs the Instagram Reels / YouTube Shorts queue for the owner's brands (channels). "
                "The studio store is the source of truth; the Google Sheet is a read-only mirror. "
                "Read tools work without a key. Write and publish tools need the owner's API key. "
                "Publishing posts for real: call it only when the owner asked, with confirm: true, or use dry_run: true.")

# ---------- redaction for calls without a key ----------

PRIVATE_KEYS = {"Google Drive Folder", "Direct MP4 Download Link", "Local Path", "spec_path", "thumb", "out_dir", "files",
                "stills", "snapshots", "ip", "account", "account_id", "connected_account_id", "log", "log_tail", "args",
                "argv", "token", "tokens", "hash", "salt", "secret", "password", "who", "pending", "unsynced", "path"}
PRIVATE_URL = re.compile(r"(https?://[^\s\"']*(?:drive\.google\.com|docs\.google\.com|googleusercontent\.com|googleapis\.com)[^\s\"']*"
                         r"|(?:https?://[^\s\"']+)?/(?:media|thumb)/[^\s\"']*)", re.I)


def redact(x):
    if isinstance(x, dict):
        return {k: redact(v) for k, v in x.items() if k not in PRIVATE_KEYS}
    if isinstance(x, list):
        return [redact(v) for v in x]
    if isinstance(x, str):
        return PRIVATE_URL.sub("[private link]", x)
    return x


# ---------- calling the /api handlers ----------

class ToolError(Exception):
    pass


async def call(ctx, handler, method="GET", path_params=None, query=None, body=None):
    """Run an /api handler with a request built from this MCP call (same user, same client IP)."""
    outer = ctx["req"]
    headers = [(k, v) for k, v in outer.scope.get("headers", []) if k in (b"cf-connecting-ip", b"user-agent")]
    payload = json.dumps(body).encode() if body is not None else b""
    if body is not None:
        headers.append((b"content-type", b"application/json"))
    q = {k: v for k, v in (query or {}).items() if v not in (None, "")}
    scope = {"type": "http", "method": method, "path": "/mcp", "headers": headers, "client": outer.scope.get("client"),
             "query_string": urllib.parse.urlencode(q).encode(), "path_params": path_params or {}, "app": outer.scope.get("app"),
             "state": {"user": ctx["user"] or "mcp-anon", "via": ctx["via"]}}

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    resp = await handler(Request(scope, receive))
    data = json.loads(resp.body or b"null")
    if resp.status_code >= 400:
        msg = data.get("error") if isinstance(data, dict) else str(data)
        raise ToolError(f"{msg} (HTTP {resp.status_code})" + (f": {json.dumps({k: v for k, v in data.items() if k != 'error'})}"
                                                              if isinstance(data, dict) and len(data) > 1 else ""))
    return data


def _app():
    from . import app
    return app


def _brand(ch):
    if not ch:
        return ""
    ch = ch.lstrip("@").lower()
    for b in K.brands():
        if ch in (b["key"], b["id_prefix"].lower(), b["sheet_tab"].lstrip("@").lower(), b["instagram"]["handle"].lstrip("@").lower()):
            return b["key"]
    raise ToolError(f"unknown channel {ch}; see list_channels")


def _id(a, k="id"):
    v = str(a.get(k, "")).strip()
    if not _app().ID_RE.match(v):
        raise ToolError(f"{k}: a Video ID like CR-108-EN")
    return v


ROW_SUMMARY = ["Video ID", "Category / Topic", "Scheduled Time (IST)", "Instagram Status", "YouTube Status",
               "Instagram Post URL", "YouTube Shorts URL", "Duration", "Format"]


async def t_list_reels(ctx, a):
    A = _app()
    d = await call(ctx, A.api_reels, query={"brand": _brand(a.get("channel")), "folder": a.get("folder"), "status": a.get("status"),
                                            "q": a.get("search")})
    reels = d["reels"]
    lo, hi = a.get("from", ""), a.get("to", "")
    if lo:
        reels = [r for r in reels if r["Scheduled Time (IST)"] >= lo]
    if hi:
        reels = [r for r in reels if r["Scheduled Time (IST)"][:len(hi)] <= hi]
    reels.sort(key=lambda r: r["Scheduled Time (IST)"])
    limit = max(1, min(500, int(a.get("limit") or 100)))
    out = [{"channel": r["brand"], "folder": r["folder"], **{h: r[h] for h in ROW_SUMMARY},
            "mirrored": not r["pending"]} for r in reels[:limit]]
    return {"count": len(reels), "returned": len(out), "now_ist": d["now"], "folders": d["counts"], "reels": out}


async def t_get_reel(ctx, a):
    d = await call(ctx, _app().api_reel, path_params={"vid": _id(a)})
    return d


async def t_list_channels(ctx, a):
    d = await call(ctx, _app().api_channels)
    return {"channels": d["channels"]}


async def t_calendar(ctx, a):
    reels = [r for r in S.list_reels() if r["Instagram Status"] != Y.ARCHIVED]
    k = _brand(a.get("channel"))
    lo, hi = a.get("from") or Y.ist_now()[:10], a.get("to") or "9999"
    days = {}
    for r in sorted(reels, key=lambda r: r["Scheduled Time (IST)"]):
        t = r["Scheduled Time (IST)"]
        if (k and r["brand"] != k) or not t or t[:10] < lo or t[:10] > hi:
            continue
        days.setdefault(t[:10], []).append({"time": t[11:], "channel": r["brand"], "id": r["Video ID"], "topic": r["Category / Topic"],
                                            "instagram": r["Instagram Status"], "youtube": r["YouTube Status"]})
    return {"from": lo, "to": hi, "days": [{"date": d, "reels": v} for d, v in days.items()]}


async def t_insights_summary(ctx, a):
    d = await call(ctx, _app().api_insights, query={"brand": _brand(a.get("channel"))})
    rows = d["rows"]
    tot = {m: sum((r.get(m) or 0) for r in rows) for m in ("views", "likes", "comments", "shares", "saves", "reach")}
    keep = lambda r: {k: r.get(k) for k in ("video_id", "brand", "posted", "permalink", "views", "likes", "comments", "shares", "saves", "reach")}
    return {"reels": len(rows), "totals": tot, "top": [keep(r) for r in d["top"]], "bottom": [keep(r) for r in d["bottom"]],
            "weeks": d["weeks"][-12:], "fetched": d["fetched"]}


JOB_PUBLIC = ("id", "kind", "title", "status", "created", "started", "ended", "exit_code", "target")


async def t_list_jobs(ctx, a):
    d = await call(ctx, _app().api_jobs, query={"limit": max(1, min(200, int(a.get("limit") or 30)))})
    return {"jobs": [{k: j.get(k) for k in JOB_PUBLIC} for j in d["jobs"]]}


async def t_get_job(ctx, a):
    j = await call(ctx, _app().api_job, path_params={"jid": int(a.get("id") or 0)})
    out = {k: j.get(k) for k in JOB_PUBLIC}
    m = re.findall(r"^POSTED (\S+) (\S+)", j.get("log_tail") or "", re.M)
    if m:
        out["posted"] = [{"id": v, "url": u} for v, u in m]
    return out


async def t_get_job_log(ctx, a):
    j = await call(ctx, _app().api_job, path_params={"jid": int(a.get("id") or 0)})
    tail = j.get("log_tail") or ""
    n = max(1000, min(200_000, int(a.get("max_chars") or 20_000)))
    return {**{k: j.get(k) for k in JOB_PUBLIC}, "log": tail[-n:]}


async def t_health(ctx, a):
    A = _app()
    local = await call(ctx, A.api_health)
    conns = await call(ctx, A.api_health_connections, query={"fresh": "1" if a.get("fresh") else ""})
    out = {"accounts": [{"channel": c["brand"], "label": c["label"], "status": c["status"], "note": c["note"]} for c in conns["accounts"]],
           "jobs_running": local.get("jobs_running"), "unmirrored_rows": local.get("pending"),
           "last_mirror": (local.get("last_mirror") or {}).get("at"), "last_snapshot": local.get("last_snapshot"),
           "scheduler": {k: (local.get("scheduler") or {}).get(k) for k in ("last_run", "age_min")},
           "canary": (local.get("canary") or {}).get("state")}
    if ctx["keyed"]:
        out["local"] = local
    return out


async def t_edit_reel(ctx, a):
    fields = a.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ToolError("fields: {Sheet header: value}, e.g. {\"Instagram Viral Caption\": \"...\"}")
    return await call(ctx, _app().api_edit, "PATCH", {"vid": _id(a)},
                      body={"fields": fields, "base": a.get("base"), "force": bool(a.get("force")), "allow_repost": bool(a.get("allow_repost"))})


async def t_schedule_reel(ctx, a):
    return await call(ctx, _app().api_schedule, "POST", {"vid": _id(a)}, body={"when": a.get("when", ""), "auto": a.get("auto", True)})


async def t_next_free_slot(ctx, a):
    return await call(ctx, _app().api_next_slot, query={"brand": _brand(a.get("channel")) or "-", "after": a.get("after"),
                                                        "n": a.get("n"), "exclude": ",".join(a.get("exclude") or [])})


async def t_hold_reel(ctx, a):
    return await call(ctx, _app().api_hold, "POST", {"vid": _id(a)}, body={"hold": a.get("hold", True) is not False})


async def t_archive_reel(ctx, a):
    return await call(ctx, _app().api_archive, "POST", {"vid": _id(a)}, body={"archive": a.get("archive", True) is not False})


async def t_swap_reels(ctx, a):
    x, y = _id(a, "a"), _id(a, "b")
    return await run_in_threadpool(Y.swap, x, y, ctx["user"], ctx["ip"])


async def t_bulk(ctx, a):
    ids = a.get("ids") or []
    if a.get("action") == "publish":
        raise ToolError("use bulk_publish to publish several reels")
    return await call(ctx, _app().api_bulk, "POST", body={"ids": ids, "action": a.get("action"), "start": a.get("start", ""),
                                                          "every_days": a.get("every_days", 1), "auto": a.get("auto", True)})


def _confirm(a):
    if not a.get("dry_run") and a.get("confirm") is not True:
        raise ToolError("publishing posts for real: send confirm: true (or dry_run: true to check without posting)")


async def _publish(ctx, a, platform):
    _confirm(a)
    return await call(ctx, _app().api_publish, "POST", body={"id": _id(a), "platform": platform, "confirm": a.get("confirm") is True,
                                                             "dry_run": bool(a.get("dry_run")), "override_cap": a.get("override_cap") is True})


async def t_publish_instagram(ctx, a):
    return await _publish(ctx, a, "instagram")


async def t_publish_youtube(ctx, a):
    return await _publish(ctx, a, "youtube")


async def t_publish_preview(ctx, a):
    return await call(ctx, _app().api_publish_preview, query={"id": _id(a), "platform": a.get("platform", "instagram")})


async def t_bulk_publish(ctx, a):
    _confirm(a)
    return await call(ctx, _app().api_bulk, "POST", body={"ids": a.get("ids") or [], "action": "publish", "platform": a.get("platform", "instagram"),
                                                          "confirm": a.get("confirm") is True, "dry_run": bool(a.get("dry_run"))})


async def t_start_job(ctx, a):
    kind = a.get("kind", "")
    if kind not in ("render", "rerender", "sync", "push", "snapshot", "dryrun", "insights", "backfill", "generate"):
        raise ToolError("kind: render, rerender, sync, push, snapshot, dryrun, insights, backfill or generate "
                        "(publish has its own tools)")
    params = dict(a.get("params") or {})
    if kind in ("render", "rerender") and a.get("stills"):
        params.update(mode="stills", stills=a["stills"])
    return await call(ctx, _app().api_job_new, "POST", body={"kind": kind, "params": params})


async def t_cancel_job(ctx, a):
    return await call(ctx, _app().api_job_cancel, "POST", {"jid": int(a.get("id") or 0)}, body={})


async def t_channel_settings(ctx, a):
    body = {"brand": _brand(a.get("channel"))}
    body.update({k: a[k] for k in K.CHANNEL_KEYS if k in a})
    return await call(ctx, _app().api_channels_save, "POST", body=body)


UPLOAD_FIELDS = ("brand", "lang", "topic", "caption", "hashtags", "yt_title", "yt_desc", "after", "when")
MAX_UPLOAD = 1024 ** 3


def _fetch_video(a, dst):
    src = str(a.get("path") or "")
    url = str(a.get("url") or "")
    if bool(src) == bool(url):
        raise ToolError("send either path (a file on the studio server) or url (http/https)")
    if src:
        p = os.path.realpath(os.path.expanduser(src))
        if not os.path.isfile(p):
            raise ToolError(f"no such file on the server: {src}")
        if os.path.getsize(p) > MAX_UPLOAD:
            raise ToolError("the file is over 1 GB")
        shutil.copyfile(p, dst)
        return os.path.getsize(dst)
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ToolError("url must be http or https")
    size = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "reels-studio"}), timeout=60) as r, open(dst, "wb") as out:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise ToolError("the download is over 1 GB")
            out.write(chunk)
    return size


async def t_upload_video(ctx, a):
    from . import upload as U
    A = _app()
    params = {k: str(a.get(k) or "") for k in UPLOAD_FIELDS}
    params["brand"] = _brand(params["brand"] or a.get("channel"))
    params["after"] = params["after"] or "draft"
    if params["after"] == "now" and a.get("confirm") is not True:
        raise ToolError("publishing right after the upload needs confirm: true")
    try:
        U.validate(params)
    except U.UploadError as e:
        raise ToolError(str(e))
    ext = os.path.splitext(urllib.parse.urlparse(str(a.get("url") or "")).path or str(a.get("path") or ""))[1].lower() or ".mp4"
    if ext not in (".mp4", ".mov"):
        raise ToolError("only MP4 or MOV files")
    d = STATE / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(8)}{ext}"
    dst = d / name
    try:
        size = await run_in_threadpool(_fetch_video, a, dst)
    except ToolError:
        dst.unlink(missing_ok=True)
        raise
    except Exception as e:
        dst.unlink(missing_ok=True)
        raise ToolError(f"could not get the video: {str(e)[:200]}")
    if size < 1024:
        dst.unlink(missing_ok=True)
        raise ToolError("the file is empty")
    params.update(file=name, who=ctx["user"])
    jid = A.STATE_REF.queue.submit("upload", params, ctx["user"])
    S.audit("upload received", name, None, {k: params[k] for k in ("brand", "after", "when", "topic")} | {"bytes": size, "via": "mcp"},
            ctx["user"], ctx["ip"])
    return {"job": jid, "file": name, "bytes": size}


async def t_list_comments(ctx, a):
    return await call(ctx, _app().api_comments, query={"brand": _brand(a.get("channel"))})


async def t_refresh_comments(ctx, a):
    return await call(ctx, _app().api_comments_refresh, "POST", body={"brand": _brand(a.get("channel"))})


async def t_reply_comment(ctx, a):
    return await call(ctx, _app().api_comments_reply, "POST", body={"brand": _brand(a.get("channel")), "comment_id": a.get("comment_id", ""),
                                                                    "message": a.get("message", ""), "send": a.get("send") is True})


async def t_mirror_push(ctx, a):
    return await call(ctx, _app().api_sync, "POST", body={})


# ---------- tool table ----------

S_ID = {"type": "string", "description": "Video ID, e.g. CR-108-EN"}
S_CH = {"type": "string", "description": "channel key (craftlayer, campusloop, ...), ID prefix or Instagram handle"}
S_TIME = {"type": "string", "description": "IST time, YYYY-MM-DD HH:MM"}
FOLDERS = ["queue", "due", "drafts", "published", "archive", "all"]


def obj(props=None, required=()):
    return {"type": "object", "properties": props or {}, "required": list(required), "additionalProperties": False}


PUB = {"id": S_ID, "confirm": {"type": "boolean", "description": "must be true to post for real"},
       "dry_run": {"type": "boolean", "description": "check everything and post nothing"},
       "override_cap": {"type": "boolean", "description": "post even if today's daily cap is reached"}}

TOOLS = [
    # name, fn, keyed, read_only, description, schema
    ("list_reels", t_list_reels, False, True, "List reels with filters. Returns a summary row per reel; use get_reel for one in full.",
     obj({"channel": S_CH, "folder": {"type": "string", "enum": FOLDERS}, "status": {"type": "string", "description": "status prefix: Ready, Hold, Published, Failed, Archived..."},
          "from": {"type": "string", "description": "scheduled at or after (YYYY-MM-DD[ HH:MM])"}, "to": {"type": "string", "description": "scheduled on or before"},
          "search": {"type": "string", "description": "words to find in any field"}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}})),
    ("get_reel", t_get_reel, False, True, "One reel: every field, its folder, publish log and insights.", obj({"id": S_ID}, ["id"])),
    ("list_channels", t_list_channels, False, True, "The channels (brands) with handles, slots, daily cap and auto-publish settings.", obj()),
    ("calendar", t_calendar, False, True, "Scheduled reels by day (archived ones left out).",
     obj({"channel": S_CH, "from": {"type": "string", "description": "YYYY-MM-DD (default today, IST)"}, "to": {"type": "string", "description": "YYYY-MM-DD"}})),
    ("insights_summary", t_insights_summary, False, True, "Instagram insights: totals, top and bottom reels, weekly views.", obj({"channel": S_CH})),
    ("list_jobs", t_list_jobs, False, True, "Recent background jobs (render, publish, upload, mirror...) and their status.",
     obj({"limit": {"type": "integer", "minimum": 1, "maximum": 200}})),
    ("get_job", t_get_job, False, True, "One job's status (and posted URLs for a finished publish job).", obj({"id": {"type": "integer"}}, ["id"])),
    ("health", t_health, False, True, "Connected / expired state of each channel's accounts, job and mirror status. No secrets.",
     obj({"fresh": {"type": "boolean", "description": "ask Composio again instead of the 10-minute cache"}})),
    ("get_job_log", t_get_job_log, True, True, "A job's log tail.", obj({"id": {"type": "integer"}, "max_chars": {"type": "integer"}}, ["id"])),
    ("publish_preview", t_publish_preview, True, True, "What publishing a reel would do and anything that blocks it. Posts nothing.",
     obj({"id": S_ID, "platform": {"type": "string", "enum": ["instagram", "youtube"]}}, ["id"])),
    ("edit_reel", t_edit_reel, True, False, "Change fields of a reel (keys are Sheet headers). Saved in the studio, then mirrored to the Sheet.",
     obj({"id": S_ID, "fields": {"type": "object", "additionalProperties": {"type": "string"}},
          "base": {"type": "object", "description": "values you read before, to detect someone else's change"},
          "force": {"type": "boolean"}, "allow_repost": {"type": "boolean", "description": "allow setting a Published status back to Ready"}}, ["id", "fields"])),
    ("schedule_reel", t_schedule_reel, True, False, "Schedule a reel at a time, or 'next' for the channel's next free slot. auto false keeps it on Hold.",
     obj({"id": S_ID, "when": {"type": "string", "description": "YYYY-MM-DD HH:MM (IST) or next"}, "auto": {"type": "boolean"}}, ["id", "when"])),
    ("next_free_slot", t_next_free_slot, True, True, "The channel's next free posting slots.",
     obj({"channel": S_CH, "after": S_TIME, "n": {"type": "integer", "minimum": 1, "maximum": 30}, "exclude": {"type": "array", "items": {"type": "string"}}}, ["channel"])),
    ("hold_reel", t_hold_reel, True, False, "Put a Ready reel on Hold (hold true) or a Hold reel back to Ready (hold false).",
     obj({"id": S_ID, "hold": {"type": "boolean"}}, ["id"])),
    ("archive_reel", t_archive_reel, True, False, "Archive a reel (never deletes; Drive folder moves to Archive/) or unarchive it (archive false).",
     obj({"id": S_ID, "archive": {"type": "boolean"}}, ["id"])),
    ("swap_reels", t_swap_reels, True, False, "Swap the scheduled times of two reels.", obj({"a": S_ID, "b": S_ID}, ["a", "b"])),
    ("bulk_action", t_bulk, True, False, "Run hold, ready, schedule, archive, unarchive, fill or swap on several reels as one job.",
     obj({"ids": {"type": "array", "items": {"type": "string"}}, "action": {"type": "string", "enum": ["hold", "ready", "schedule", "archive", "unarchive", "fill", "swap"]},
          "start": S_TIME, "every_days": {"type": "integer"}, "auto": {"type": "boolean"}}, ["ids", "action"])),
    ("publish_instagram", t_publish_instagram, True, False, "Publish one reel to Instagram now. Needs confirm: true; dry_run: true posts nothing.",
     obj(PUB, ["id"])),
    ("publish_youtube", t_publish_youtube, True, False, "Upload one reel to YouTube Shorts now. Needs confirm: true; dry_run: true posts nothing.",
     obj({k: v for k, v in PUB.items() if k != "override_cap"}, ["id"])),
    ("bulk_publish", t_bulk_publish, True, False, "Publish several reels now, one after another in one job. Needs confirm: true.",
     obj({"ids": {"type": "array", "items": {"type": "string"}}, "platform": {"type": "string", "enum": ["instagram", "youtube"]},
          "confirm": {"type": "boolean"}, "dry_run": {"type": "boolean"}}, ["ids"])),
    ("start_job", t_start_job, True, False, "Start a background job: render/rerender (params.spec, params.mode full|stills|only), "
     "sync (Drive + studio row for params.spec), push (Sheet mirror), snapshot, dryrun, insights (params.brand), backfill, generate.",
     obj({"kind": {"type": "string"}, "params": {"type": "object"}, "stills": {"type": "string", "description": "seconds for stills, e.g. 0.3,7,14"}}, ["kind"])),
    ("cancel_job", t_cancel_job, True, False, "Cancel a queued or running job.", obj({"id": {"type": "integer"}}, ["id"])),
    ("channel_settings", t_channel_settings, True, False, "Change a channel's auto_publish, youtube_auto, slots (HH:MM list) or daily cap.",
     obj({"channel": S_CH, "auto_publish": {"type": "boolean"}, "youtube_auto": {"type": "boolean"},
          "slots": {"type": "array", "items": {"type": "string"}}, "cap": {"type": "integer"}}, ["channel"])),
    ("upload_video", t_upload_video, True, False, "Add a finished MP4/MOV from a file on the studio server (path) or a URL. after: draft (Hold), "
     "schedule (needs when), next (next free slot) or now (publishes; needs confirm).",
     obj({"path": {"type": "string"}, "url": {"type": "string"}, "channel": S_CH, "lang": {"type": "string"}, "topic": {"type": "string"},
          "caption": {"type": "string"}, "hashtags": {"type": "string"}, "yt_title": {"type": "string"}, "yt_desc": {"type": "string"},
          "after": {"type": "string", "enum": ["draft", "schedule", "next", "now"]}, "when": S_TIME, "confirm": {"type": "boolean"}}, ["channel", "topic"])),
    ("list_comments", t_list_comments, True, True, "Cached Instagram comments for a channel.", obj({"channel": S_CH}, ["channel"])),
    ("refresh_comments", t_refresh_comments, True, False, "Fetch the latest Instagram comments for a channel.", obj({"channel": S_CH}, ["channel"])),
    ("reply_comment", t_reply_comment, True, False, "Reply to an Instagram comment. Needs send: true.",
     obj({"channel": S_CH, "comment_id": {"type": "string"}, "message": {"type": "string"}, "send": {"type": "boolean"}}, ["channel", "comment_id", "message"])),
    ("mirror_push", t_mirror_push, True, False, "Push rows waiting for the Google Sheet mirror now.", obj()),
]
BY_NAME = {t[0]: t for t in TOOLS}


def tool_list():
    out = []
    for name, _, keyed, ro, desc, schema in TOOLS:
        out.append({"name": name, "description": desc + (" Requires API key." if keyed else " Works without a key (private fields hidden)."),
                    "inputSchema": schema,
                    "annotations": {"readOnlyHint": ro, "destructiveHint": name.startswith(("publish_", "bulk_publish", "archive")),
                                    "openWorldHint": name.startswith(("publish_", "bulk_publish", "reply_", "upload_"))}})
    return out


# ---------- JSON-RPC ----------

def _err(rid, code, msg):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}


async def dispatch(ctx, msg):
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _err(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid JSON-RPC request")
    rid, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    if "id" not in msg:                       # a notification (initialized, cancelled...): nothing to answer
        return None
    if method == "initialize":
        want = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": want if want in PROTOCOLS else PROTOCOLS[0],
            "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER,
            "instructions": INSTRUCTIONS + (" You are using the API key." if ctx["keyed"] else " No key: read-only.")}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tool_list()}}
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        t = BY_NAME.get(name)
        if not t:
            return _err(rid, -32602, f"unknown tool {name}")
        if not isinstance(args, dict):
            return _err(rid, -32602, "arguments must be an object")
        _, fn, keyed, _, _, _ = t
        if keyed and not ctx["keyed"]:
            why = ctx.get("key_problem") or "no API key was sent"
            return {"jsonrpc": "2.0", "id": rid, "result": _result({"error": f"{name} requires API key ({why}). Send Authorization: Bearer <key>, "
                                                                            "X-API-Key: <key> or ?api_key=<key>."}, True)}
        try:
            data = await fn(ctx, args)
            err = False
        except ToolError as e:
            data, err = {"error": str(e)}, True
        except (ValueError, TypeError) as e:
            data, err = {"error": f"bad arguments: {e}"}, True
        if ctx["keyed"]:
            S.audit(f"mcp {name}", str(args.get("id") or args.get("channel") or args.get("ids") or "")[:200], None,
                    {"args": {k: v for k, v in args.items() if k not in ("message", "fields", "caption")} | ({"fields": list(args["fields"])} if isinstance(args.get("fields"), dict) else {}),
                     "error": data.get("error") if err else None}, ctx["user"], ctx["ip"])
        else:
            data = redact(data)
        return {"jsonrpc": "2.0", "id": rid, "result": _result(data, err)}
    return _err(rid, -32601, f"method not found: {method}")


def _result(data, is_error):
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=1)}],
            "structuredContent": data if isinstance(data, dict) else {"result": data}, "isError": is_error}


ALLOWED_ORIGINS = ("https://studio.campusloop.space", "http://127.0.0.1", "http://localhost")


def _reply(req, payload, headers=None):
    """JSON, or one SSE `message` event when the client accepts only text/event-stream."""
    accept = req.headers.get("accept", "")
    headers = {"cache-control": "no-store", **(headers or {})}
    if "text/event-stream" in accept and "application/json" not in accept and "*/*" not in accept:
        body = "event: message\ndata: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
        return Response(body, media_type="text/event-stream", headers={**headers, "x-accel-buffering": "no"})
    return JSONResponse(payload, headers=headers)


async def handle(req):
    if req.method == "DELETE":
        return Response(status_code=200, headers={"cache-control": "no-store"})   # sessions hold no state here
    if req.method != "POST":
        return Response(status_code=405, headers={"allow": "POST, DELETE", "cache-control": "no-store"})
    origin = req.headers.get("origin", "")
    if origin and not origin.startswith(ALLOWED_ORIGINS):       # DNS-rebinding guard from the MCP transport spec
        return JSONResponse(_err(None, -32000, "origin not allowed"), status_code=403)
    try:
        msg = await req.json()
    except Exception:
        return JSONResponse(_err(None, -32700, "parse error: send a JSON-RPC object"), status_code=400)
    st = req.scope.get("state", {})
    via = st.get("via")
    keyed = via in ("key", "token")                             # a browser cookie is not a key here (no CSRF on /mcp)
    from .app import client_ip
    ctx = {"req": req, "keyed": keyed, "user": st.get("user") if keyed else None, "via": via if keyed else None, "ip": client_ip(req),
           "key_problem": st.get("key_problem", "")}
    if isinstance(msg, list):
        out = [r for r in [await dispatch(ctx, m) for m in msg] if r is not None]
        return _reply(req, out) if out else Response(status_code=202)
    res = await dispatch(ctx, msg)
    if res is None:
        return Response(status_code=202)
    extra = {}
    if isinstance(msg, dict) and msg.get("method") == "initialize":
        extra["mcp-session-id"] = req.headers.get("mcp-session-id") or secrets.token_hex(16)
    return _reply(req, res, extra)
