# Reels Studio

A password-protected web dashboard over this repo: every reel of every brand, its Sheet row, player, publish
buttons, calendar, board, jobs, script studio, insights, comments inbox, health, sound and the FilmCraft editor.
It imports the `ops/` modules instead of rewriting them, so the Sheet, the scheduler and the publishers behave
exactly as they do from the terminal and from cron.

- Local: http://127.0.0.1:4820 (uvicorn binds to 127.0.0.1 only)
- Public: https://studio.campusloop.space, through its own Cloudflare tunnel (`~/.cloudflared/reels-studio.yml`)

## Start and stop

```bash
bash ops/studio_service.sh start     # web app + tunnel (tunnel only if ~/.cloudflared/reels-studio.yml exists)
bash ops/studio_service.sh status
bash ops/studio_service.sh logs
bash ops/studio_service.sh stop      # stops the web app and the studio tunnel only; other tunnels are untouched
python3.11 -m studio                 # foreground, for debugging
```

`bash ops/install_cron.sh` adds a watchdog (every 15 minutes and at boot), a Sheet → local sync every 5 minutes and a
nightly snapshot at 03:15, next to the publisher line.

## Login

- First start generates a password, prints it once and writes it to `~/.config/reels-studio/initial-password.txt`
  (mode 600). Change it in Settings (that deletes the file) or with `python3.11 -m studio password`.
- `~/.config/reels-studio/auth.json` (mode 600) holds only the scrypt hash, the cookie signing secret and hashed API
  tokens. Changing the password rotates the secret, which signs every session out.
- Session cookie: signed (HMAC-SHA256), HttpOnly, SameSite=Lax, 14 days; `Secure` when the request came over HTTPS
  (directly or via `X-Forwarded-Proto` / `CF-Visitor` from the tunnel), so plain http://127.0.0.1 still works.
- Every POST/PATCH with a cookie needs `X-CSRF-Token` (from `GET /api/session` or the login response).
- Failed logins: 5 per IP (`CF-Connecting-IP`) and 30 overall per 15 minutes, then 429.
- Optional: put the hostname behind Cloudflare Access (email one-time codes) as a second gate.

## Data

- Store: SQLite `~/.local/state/reels-shorts/studio.db` (tables `reels` (with the local-only `prev_status`), `publish_log`, `insights`, `jobs`, `audit`,
  `settings`, `comments_cache`). **It is the source of truth.** The Google Sheet is a read-only mirror for other agents.
- Every change (UI, `/api`, `/mcp`, the scheduler's status marks, `ops/make.py --sync-only`, `ops/clip.py`, uploads,
  restores) is written to the store first. The changed cells are queued (`pending`) and the whole row is written to
  the Sheet by Video ID (`ops/sheet.write_row`), in the background. A Sheet failure never blocks or rolls back a change;
  the queued cells show "mirror waiting" and are retried by the next push.
- Mirror push: `python3.11 -m studio.sync push` (cron every 5 minutes, and after each change). `pull` is an old alias of
  `push`: nothing reads the Sheet back automatically.
- Import from Sheet (Settings, or `python3.11 -m studio.sync import [--tab T]`): a diff of cells that differ and rows
  that exist only in the Sheet. Only the ticked items are applied. `--apply-all` was used once, for the migration.
- The scheduler (`ops/scheduler.py`) reads due rows from the store through `ops/reelrows.py` and writes
  Publishing / Published / Failed there first, then mirrors that row.
- An edit can carry `base` (the values the editor loaded); a cell changed in the studio since then answers 409.
- Setting a Published row back to Ready needs `allow_repost: true`; rows that are `Publishing` can not be edited.
- Snapshots (the store's backup): `python3.11 -m studio.sync snapshot` writes JSON + CSV of every tab and a copy of `publish-log.jsonl` to
  `~/.local/state/reels-shorts/backup/YYYY-MM-DD/`, keeping 30 days. "Restore row" rewrites one row from a snapshot;
  status and post-URL cells that already hold a value are never rolled back.
- Job logs: `~/.local/state/reels-shorts/studio-jobs/<id>.log`.

## Library

- Folders, computed from the row (the Sheet stays the source of truth): **Queue** (Ready, in the future), **Due / Failed**
  (Ready and overdue, Failed, Manual upload needed), **Drafts** (Hold and anything else, plus renders that are not in the
  Sheet yet), **Published** (Instagram Published), **Archive** (status `Archived`), **All**. Counts per channel.
- Channel switcher at the top: one pill per channel plus All; it filters Library, Calendar, Board, Insights and Comments,
  is kept in the URL (`#/library?ch=craftlayer`) and in localStorage; keys `1`-`4`, `0` for All.
- **Archive** sets both status cells to `Archived` (Sheet first, through `sync.edit`), keeps the previous values in the
  local `prev_status` column and moves the reel's Drive folder into `Archive/` under the reels folder. Nothing is deleted.
  **Unarchive** puts the previous status back; a Ready reel whose slot has passed comes back as Hold, so cron never posts
  it at once. A published reel's folder goes back to `Published/`.
- **Schedule** (cards and drawer): date and time in IST, chips for next free slot, today and tomorrow, and either
  auto-publish (Ready) or just plan (Hold). A Published reel can not be rescheduled. "Next free slot" uses the
  channel's slot times and daily cap and skips slots that a Ready row already holds.
- Queue timeline: one row per day, one lane per slot, `+ fill` on empty slots, drag one reel onto another to swap their
  times (two audited Sheet edits in one job), drop onto a free slot to move it.
- Bulk bar (bottom): Hold, Ready, Fill next free slots, Schedule from … every N days, Archive or Unarchive, Publish
  selected now (one confirm, one sequential job). Shift-click selects a range, Ctrl/Cmd+A the whole folder.
- **Upload** (Library header): MP4 or MOV up to 1 GB and 90 s, channel, language, topic, caption, hashtags, YouTube
  fields when the channel has YouTube, and after upload: draft (Hold), next free slot, schedule at, or publish now. The
  `upload` job (`studio/upload.py`) gives it an id like `CR-U001-EN`, saves `out/<brand>/<ID>/<id>.mp4`, re-encodes it to
  1080×1920 h264/aac 30 fps at −14 LUFS when needed, writes `thumb.jpg`, archives it to Drive and writes the Sheet row.

## Channels (auto-publish)

Settings → Channels, per brand: auto-publish on/off (the master switch for cron), YouTube auto-upload, slot times and
daily cap. Stored in `~/.local/state/reels-shorts/channels.json`; `ops/config.brand()` lays it over `brand.json`, so cron,
the CLI and the studio read the same values. With auto-publish off the scheduler skips that channel except for ids it
is forced to post (Publish now). Every change is in the audit log. The top bar shows a red "Auto-publish OFF" chip.

After an Instagram post the scheduler moves the reel's Drive folder into `Published/` (best effort; a Drive error never
stops a post). `python3.11 -m studio.sync backfill-published` (or the button in Settings) moves the older ones.

## Publishing

Every card, table row and the drawer has a two-click **Publish to Instagram now** (and **Upload to YouTube now** where the
channel has YouTube): the first click turns it into "Confirm? @handle" for 4 seconds, the second sends
`{confirm: true}`. A spinner shows each step; then the card shows an "Open IG" link and moves to
Published, or the error with Retry. Ready, Hold, Failed, Manual and draft rows can be pushed this way; Published,
Publishing, Archived and channel-less rows never.

`POST /api/publish {id, platform, confirm: true}` queues a job that runs `python3.11 -m studio.publish_job`. A manual
publish is a **direct call**, not a scheduler run:

1. It takes the scheduler's lock (`scheduler.lock`), so cron and the button never post at the same time. If cron holds
   it, the job waits up to 60 s, then stops with a clear message (nothing posted).
2. It sets the row to `Publishing` (store first, then the Sheet mirror).
3. It calls the channel's posting backend directly (`ops/publish_backends.py`; `composio` runs
   `ops/publish_instagram.publish` or `ops/publish_youtube.upload`).
4. It writes `Published` + the URL, or `Failed: reason`, adds a publish-log line (`via: publish-now`) and mirrors the row.

The schedule time, slots, daily cap and auto-publish switch are not used and not changed. The job log and the card's
spinner show each step: `uploading video to Composio…`, `Instagram container <id> created, processing…`,
`publishing…`, `published <permalink>`. Several ids run one after another under the same lock (bulk publish).
`dry_run: true` checks everything and posts nothing.

Cancel safety: from the upload until the result is written, the job ignores Cancel (SIGTERM). A cancelled publish job
is never force-killed, and reels not started yet are skipped. The container id goes into the publish log as soon as it
exists.

Stuck rows: `python3.11 -m studio.publish_job --reconcile` runs on the 5-minute cron tick and at studio start. It
looks at Instagram rows at `Publishing` for over 10 minutes with no running publish job. It reads the channel's 10
newest media (`INSTAGRAM_GET_IG_USER_MEDIA`) and compares the first 60 characters of the caption (whitespace and
`%23` normalised). A match becomes `Published` with that permalink; no match becomes
`Failed: interrupted, not found on Instagram`. A stuck card has a **Check Instagram** button
(`POST /api/reels/{id}/check-instagram`, MCP `check_instagram`) that does this at once.

Posting method: Settings → Channels → "Posts via" (`publish_backend`: `composio`, the default; `metricool` is a stub
until that connector is enabled). Cron posts go through the same backend.

## JSON API (agents)

Create a token in Settings or with `python3.11 -m studio token <name>`, then send `Authorization: Bearer <token>`
(no CSRF header needed). Every call is audited as `token:<name>`. The MCP key (below) works here too, as
`Authorization: Bearer <key>` or `X-API-Key: <key>`, audited as `mcp-key`. Neither works on `/api/settings/*`
(password, tokens, the key): those need the owner's browser session.

| Method | Path | What |
|---|---|---|
| GET | `/api/reels?brand=&status=&folder=&q=` | every row (Sheet header names + `tab`, `brand`, `folder`, `pending`, `missing`, `thumb`, `spec_path`, `prev_status`), folder counts per brand, unsynced renders |
| GET | `/api/reels/{id}` | one row + publish log, insights, files, stills, spec summary, snapshots |
| PATCH | `/api/reels/{id}` | `{fields: {header: value}, base?, force?, allow_repost?}` → 200 ok, 409 conflict |
| POST | `/api/reels/{id}/hold` | `{hold: true/false}` Ready ↔ Hold |
| POST | `/api/reels/{id}/archive` | `{archive: true/false}` archive / unarchive |
| POST | `/api/reels/{id}/schedule` | `{when: "YYYY-MM-DD HH:MM" or "next", auto: true/false}` Ready or Hold at that time |
| GET | `/api/slots/next?brand=&after=&exclude=&n=` | next free slot(s) of a channel |
| GET/POST | `/api/channels` | channel settings / `{brand, auto_publish?, youtube_auto?, slots?, cap?, publish_backend?}` |
| POST | `/api/reels/{id}/check-instagram` | settle a row stuck at Publishing (looks for it on Instagram by caption) |
| POST | `/api/upload` | multipart `file` + `brand, lang, topic, caption, hashtags, yt_title, yt_desc, after, when, confirm` (a job) |
| POST | `/api/reels/bulk` | `{ids, action: hold/ready/schedule/fill/swap/archive/unarchive/publish, start, every_days, confirm}` (a job) |
| GET/POST | `/api/reels/{id}/restore` | `?date=YYYY-MM-DD` dry run / `{date, dry_run: false}` |
| POST | `/api/sync` | push the Sheet mirror now (a job) |
| GET/POST | `/api/import/preview?tab=`, `/api/import/apply` | Sheet → studio diff / `{tab, changes: {id: [header]}, new: [id]}` |
| GET | `/api/publish/preview?id=&platform=` | handle, caption, cap, today's count, problems, lock state |
| POST | `/api/publish` | `{id, platform, confirm: true, dry_run?}` (a job; a direct post, the daily cap does not apply) |
| GET/POST | `/api/jobs` | list / `{kind, params}`: `render`, `rerender`, `sync`, `generate`, `insights`, `push`, `snapshot`, `dryrun`, `backfill` |
| GET | `/api/jobs/{id}`, `/api/jobs/{id}/stream` | status + log tail / live log (SSE) |
| POST | `/api/jobs/{id}/cancel` | cancel |
| GET/POST | `/api/scripts`, `/api/scripts/check`, `/api/scripts/save` | CraftLayer script studio |
| GET/POST | `/api/insights`, `/api/insights/fetch` | `{brand, sheet?}` |
| GET/POST | `/api/comments?brand=`, `/api/comments/refresh`, `/api/comments/reply` | reply needs `send: true` |
| GET | `/api/health`, `/api/health/connections` | local health / Composio connection status |
| GET/POST | `/api/sound`, `/api/sound/make`, `/api/sound/use`, `/api/sound/brand` | SFX packs, earshot |
| GET | `/api/audit`, `/api/brands`, `/api/snapshots`, `/api/unsynced` | |
| GET | `/media/<brand>/<ID>/<file>`, `/thumb/<ID>.jpg` | MP4 (range requests), images, captions |
| GET | `/editor/` | FilmCraft web build, with COOP/COEP headers |

## Files (temporary hosting)

The Files page hosts any file at an unguessable public link, `https://studio.campusloop.space/f/<token>/<name>`. The
token is 43 random URL-safe characters; the name in the link is cosmetic. Files sit in folders and expire after
1 day, 1 week (the default), a custom time up to 90 days ahead, or never. Never is for the owner's session and the
MCP key only, not agent tokens.

- **Who:** uploading, listing, renaming, moving, replacing, changing expiry and deleting need the owner's login or the
  API key; anonymous requests get 401. Only a file's own link is public.
- **Safe serving on `/f/`:**
  - Images (PNG, JPEG, GIF, WebP, AVIF), audio, video, PDF and plain text open inline.
  - Everything else, including HTML, SVG and JS, is sent as `application/octet-stream` with
    `Content-Disposition: attachment`, so it never renders on the studio origin.
  - Every response has `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox; default-src 'none'` and
    `Referrer-Policy: no-referrer`.
  - No cookie is read or set and there is no login redirect. Range requests work.
- **Storage:** content is kept by a random id in `~/.local/state/reels-shorts/files/` (mode 700) and metadata in the
  studio store (`files_meta`, `file_folders`). Names are cleaned (no directories, control characters or leading dots)
  and never touch the filesystem, so no path traversal is possible.
- **Limits:** 1 GB per file through the UI and REST (streamed), 25 MB of base64 over MCP. The total quota defaults to
  20 GB (Files, then Quota); a full store answers 507 "storage is full".
- **Expiry:** `python3.11 -m studio.files sweep` runs on the 5-minute cron tick and at studio start. An expired link
  answers 404 at once.
- **Audit:** every write is in the audit log (file uploaded, changed, replaced, deleted, expired; folder created,
  changed, deleted; quota).

| Method | Path | What |
|---|---|---|
| GET | `/api/files?folder=&q=&all=1` | files in a folder (or matching q anywhere), the folder tree, usage |
| POST | `/api/files` | multipart `file`, `folder_id?`, `expiry?` (1d, 7d, `YYYY-MM-DD HH:MM` IST, never) |
| GET/PATCH/DELETE | `/api/files/{id}` | info / `{name?, folder_id?, expiry?, new_link?}` / delete |
| PUT | `/api/files/{id}/content` | multipart `file`: replace the content, same link |
| POST | `/api/folders` | `{name, parent_id?}` |
| PATCH/DELETE | `/api/folders/{id}` | `{name?, parent_id?}` / delete (`?confirm=true` when it is not empty) |
| POST | `/api/files/quota` | `{quota_gb}` |

MCP (key only): `upload_file` (`content_base64` up to 25 MB or a public `url`), `list_files`, `get_file`, `update_file`
(rename, move, expiry, `new_link`, replace content), `delete_file`, `create_folder`, `rename_folder`, `move_folder`,
`delete_folder` (`confirm: true` when it is not empty). URL fetches refuse private and loopback addresses.

## MCP

`https://studio.campusloop.space/mcp` is an MCP server (Streamable HTTP, JSON-RPC 2.0 over `POST`, protocol
`2025-06-18`, also `2025-03-26` and `2024-11-05`). It answers `initialize` (with an `Mcp-Session-Id` header, never
required afterwards), `ping`, `tools/list` and `tools/call`; notifications get 202. Replies are JSON, or one SSE
`message` event when the client accepts only `text/event-stream`. `GET /mcp` is 405. `/.well-known/*` is a JSON 404:
there is no OAuth.

- **No key**: every tool is listed, but only the read tools run (`list_reels`, `get_reel`, `list_channels`,
  `calendar`, `insights_summary`, `list_jobs`, `get_job`, `health`). Private fields are removed: Drive folder and direct
  MP4 links, `/media` and `/thumb` URLs, local paths, audit IPs, Composio account ids, job logs. Other tools answer
  `isError: true` with "requires API key" (not HTTP 401, so connectors still see the tools).
- **With the key**: every UI action. Edit fields, schedule (time or `next`), next free slot, hold, archive, swap, bulk
  actions, `publish_instagram` / `publish_youtube` / `bulk_publish`, render, stills, sync and mirror jobs, job logs,
  channel settings, `upload_video` (a file on the server or a URL), comments and replies, and the unredacted reads.
  Each call is audited as `mcp-key`.
- **Publishing posts for real.** The publish tools need `confirm: true`; `dry_run: true` checks and posts nothing. They run
  as the same publish job as the UI, under the scheduler's shared lock and daily cap (`override_cap: true` to pass it).
- Send the key as `Authorization: Bearer <key>`, `X-API-Key: <key>`, or `?api_key=<key>` (only for connectors that take
  nothing but a URL; a key in a URL can end up in logs). Ten bad keys from one IP lock that IP out for 15 minutes.

Key: only its scrypt hash is stored, in `~/.config/reels-studio/auth.json`. Set it from the environment, rotate it
(Settings → MCP server, the new key is shown once) or revoke it:

```bash
STUDIO_MCP_KEY='<your key, 24+ characters>' python3.11 -m studio mcp-key
python3.11 -m studio mcp-key --revoke
```

Client config (Claude Code, Cursor and others that take `mcpServers`):

```json
{
  "mcpServers": {
    "reels-studio": {
      "type": "http",
      "url": "https://studio.campusloop.space/mcp",
      "headers": { "Authorization": "Bearer YOUR_STUDIO_MCP_KEY" }
    }
  }
}
```

Check it: `npx -y @modelcontextprotocol/inspector --cli https://studio.campusloop.space/mcp --transport http --method tools/list`.

## Files

`app.py` routes, auth guard, media, SSE · `auth.py` scrypt, cookies, CSRF, tokens, rate limit · `store.py` SQLite ·
`sync.py` store-first edits, Sheet mirror push, import diff, snapshots, restore, bulk, folders, archive, slots, swap ·
`mcp.py` the MCP server (tools, redaction, JSON-RPC) · `files.py` temporary file hosting · `jobs.py`
subprocess queue · `publish_job.py` one or more reels through `scheduler.run` · `upload.py` the upload job · `tasks.py` insights, comments, health · `web/` static UI (vanilla JS modules, no build).

Tests: `python3.11 -m pytest tests/studio` (no network; Composio and the Sheet are mocked).
