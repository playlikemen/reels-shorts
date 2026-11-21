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

- Store: SQLite `~/.local/state/reels-shorts/studio.db` (tables `reels`, `publish_log`, `insights`, `jobs`, `audit`,
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

## Publishing

`POST /api/publish {id, platform, confirm: true}` queues a job that runs `python3.11 -m studio.publish_job`, which:

1. takes the scheduler's own lock (`scheduler.lock`), so cron and the button can never post at the same time;
2. narrows `ops/scheduler.run` to this one row and platform (the other platform's status is hidden in memory only);
3. calls `scheduler.run(publish=True, force={id})`: the row becomes `Publishing` before the API call, then
   `Published` or `Failed: ...`, and the publish log is written, exactly as for a cron post.

Only rows whose status is `Ready` are posted. If the brand's daily cap is reached, the request also needs
`override_cap: true`. `dry_run: true` shows what would be posted, without posting. After the job, the tab is pulled
again.

## JSON API (agents)

Create a token in Settings or with `python3.11 -m studio token <name>`, then send `Authorization: Bearer <token>`
(no CSRF header needed). Every call is audited as `token:<name>`.

| Method | Path | What |
|---|---|---|
| GET | `/api/reels?brand=&status=&q=` | every row (Sheet header names + `tab`, `brand`, `pending`, `missing`, `thumb`, `spec_path`) and unsynced renders |
| GET | `/api/reels/{id}` | one row + publish log, insights, files, stills, spec summary, snapshots |
| PATCH | `/api/reels/{id}` | `{fields: {header: value}, base?, force?, allow_repost?}` → 200 ok, 202 pending, 409 conflict |
| POST | `/api/reels/{id}/hold` | `{hold: true/false}` Ready ↔ Hold |
| POST | `/api/reels/bulk` | `{ids, action: hold/ready/schedule, start, every_days}` (a job) |
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
`sync.py` pull, edit, conflicts, pending, snapshots, restore, bulk · `jobs.py` subprocess queue · `publish_job.py` one
reel through `scheduler.run` · `tasks.py` insights, comments, health · `web/` static UI (vanilla JS modules, no build).

Tests: `python3.11 -m pytest tests/studio` (no network; Composio and the Sheet are mocked).
