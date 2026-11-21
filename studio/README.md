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
  `settings`, `comments_cache`). It is the local backup of the Sheet.
- Pull (`python3.11 -m studio.sync pull`): `ops/sheet.rows()` per tab, upsert by Video ID. A row that vanished from
  the Sheet is kept and flagged "missing in sheet", never deleted.
- Edit: the row is re-read, the Sheet is written first (`ops/sheet.set_cells`), then the store. If a cell changed in
  the Sheet since the editor loaded it, the API answers 409 with both values. If the Sheet write fails, the edit is
  kept as "pending sync" and retried by the next pull.
- Setting a Published row back to Ready needs `allow_repost: true`; rows that are `Publishing` can not be edited.
- Snapshots: `python3.11 -m studio.sync snapshot` writes JSON + CSV of every tab and a copy of `publish-log.jsonl` to
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
`{confirm: true, override_cap: true}`. A spinner runs in place; then the card shows an "Open IG" link and moves to
Published, or the error with Retry. Ready, Hold, Failed, Manual and draft rows can be pushed this way; Published,
Publishing, Archived and channel-less rows never.

`POST /api/publish {id, platform, confirm: true}` queues a job that runs `python3.11 -m studio.publish_job`, which:

1. takes the scheduler's own lock (`scheduler.lock`), so cron and the button can never post at the same time;
2. narrows `ops/scheduler.run` to this one row and platform (the other platform's status is hidden in memory only);
3. calls `scheduler.run(publish=True, force={id})`: the row becomes `Publishing` before the API call, then
   `Published` or `Failed: ...`, and the publish log is written, exactly as for a cron post. A Hold, Failed or draft row
   is shown to the scheduler as Ready for this one forced run only (in memory), so its status flips through the same path.

Several ids run one after another under the same lock (bulk publish). If the brand's daily cap is reached, the request also needs
`override_cap: true`. `dry_run: true` shows what would be posted, without posting. After the job, the tab is pulled
again.

## JSON API (agents)

Create a token in Settings or with `python3.11 -m studio token <name>`, then send `Authorization: Bearer <token>`
(no CSRF header needed). Every call is audited as `token:<name>`.

| Method | Path | What |
|---|---|---|
| GET | `/api/reels?brand=&status=&folder=&q=` | every row (Sheet header names + `tab`, `brand`, `folder`, `pending`, `missing`, `thumb`, `spec_path`, `prev_status`), folder counts per brand, unsynced renders |
| GET | `/api/reels/{id}` | one row + publish log, insights, files, stills, spec summary, snapshots |
| PATCH | `/api/reels/{id}` | `{fields: {header: value}, base?, force?, allow_repost?}` → 200 ok, 202 pending, 409 conflict |
| POST | `/api/reels/{id}/hold` | `{hold: true/false}` Ready ↔ Hold |
| POST | `/api/reels/{id}/archive` | `{archive: true/false}` archive / unarchive |
| POST | `/api/reels/{id}/schedule` | `{when: "YYYY-MM-DD HH:MM" or "next", auto: true/false}` Ready or Hold at that time |
| GET | `/api/slots/next?brand=&after=&exclude=&n=` | next free slot(s) of a channel |
| GET/POST | `/api/channels` | channel settings / `{brand, auto_publish?, youtube_auto?, slots?, cap?}` |
| POST | `/api/upload` | multipart `file` + `brand, lang, topic, caption, hashtags, yt_title, yt_desc, after, when, confirm` (a job) |
| POST | `/api/reels/bulk` | `{ids, action: hold/ready/schedule/fill/swap/archive/unarchive/publish, start, every_days, confirm}` (a job) |
| GET/POST | `/api/reels/{id}/restore` | `?date=YYYY-MM-DD` dry run / `{date, dry_run: false}` |
| POST | `/api/sync` | pull from the Sheet now (a job) |
| GET | `/api/publish/preview?id=&platform=` | handle, caption, cap, today's count, problems, lock state |
| POST | `/api/publish` | `{id, platform, confirm: true, override_cap?, dry_run?}` (a job) |
| GET/POST | `/api/jobs` | list / `{kind, params}`: `render`, `rerender`, `sync`, `generate`, `insights`, `pull`, `snapshot`, `dryrun` |
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

## Files

`app.py` routes, auth guard, media, SSE · `auth.py` scrypt, cookies, CSRF, tokens, rate limit · `store.py` SQLite ·
`sync.py` pull, edit, conflicts, pending, snapshots, restore, bulk, folders, archive, slots, swap · `jobs.py`
subprocess queue · `publish_job.py` one or more reels through `scheduler.run` · `upload.py` the upload job · `tasks.py` insights, comments, health · `web/` static UI (vanilla JS modules, no build).

Tests: `python3.11 -m pytest tests/studio` (no network; Composio and the Sheet are mocked).
