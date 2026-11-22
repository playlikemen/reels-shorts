// Health: connections, cron heartbeat, YouTube canary, disk, sync state, tunnel.
import { h, api, post, button, busy, jobToast, fmtBytes, ago } from "../app.js";

export async function render(root) {
  const conn = h("div.panel", {}, h("h2", {}, "Connections"), h("p.muted", {}, "Checking Composio…"));
  const body = h("div");
  root.append(h("header.page", {}, h("h1", {}, "Health"),
    button("Snapshot now", (e) => busy(e.target, async () => { const r = await post("/api/jobs", { kind: "snapshot" }); jobToast(r.job, "Snapshot"); })),
    button("Dry run scheduler", (e) => busy(e.target, async () => { const r = await post("/api/jobs", { kind: "dryrun" }); location.hash = `#/jobs/${r.job}`; }))), body, conn);
  const d = await api("/api/health");
  const s = d.scheduler;
  const stale = s.age_min == null || s.age_min > 20;
  body.append(
    h("div.stats", {},
      stat("Cron heartbeat", s.age_min == null ? "never" : `${s.age_min} min ago`, stale ? "bad" : "ok"),
      stat("YouTube canary", d.canary.state, d.canary.state === "blocked" ? "bad" : d.canary.state === "pending" ? "warn" : "ok"),
      stat("Last Sheet mirror", d.last_pull ? ago(d.last_pull.at) : "never"),
      stat("Pending edits", d.pending, d.pending ? "warn" : "ok"),
      stat("Missing in sheet", d.missing, d.missing ? "bad" : "ok"),
      stat("out/ size", fmtBytes(d.out_bytes)),
      stat("Disk free", `${fmtBytes(d.disk_free)} of ${fmtBytes(d.disk_total)}`),
      stat("Tunnel", d.tunnel.running ? "running" : d.tunnel.configured ? "configured, not running" : "not configured", d.tunnel.running ? "ok" : "warn"),
      stat("Jobs running", d.jobs_running),
      stat("Last snapshot", d.last_snapshot ? ago(d.last_snapshot.at) : "never")),
    h("div.grid2", {},
      h("div.panel", {}, h("h2", {}, "Scheduler log (tail)"), h("pre.log", {}, (s.tail || []).join("\n") || "(empty)"),
        h("h3", { style: { margin: "12px 0 6px" } }, "Cron lines"), s.cron_lines.length ? h("pre.log", {}, s.cron_lines.join("\n")) : h("p.muted", {}, "No reels-shorts cron lines installed.")),
      h("div.panel", {}, h("h2", {}, "This host"),
        h("dl.kv", {},
          h("dt", {}, "Public URL"), h("dd", {}, d.tunnel.hostname ? h("a", { href: `https://${d.tunnel.hostname}`, target: "_blank", rel: "noopener" }, d.tunnel.hostname) : "—"),
          h("dt", {}, "Canary"), h("dd", { class: "mono" }, JSON.stringify(d.canary)),
          h("dt", {}, "Editor"), h("dd", {}, d.filmcraft ? h("a", { href: "/editor/", target: "_blank" }, "FilmCraft web ↗") : "not installed"),
          h("dt", {}, "earshot"), h("dd", {}, d.earshot ? "installed" : "not installed"),
          h("dt", {}, "Last mirror result"), h("dd", { class: "mono small" }, JSON.stringify(d.last_pull?.summary || {}))))));
  try {
    const c = await api("/api/health/connections");
    conn.replaceChildren(h("div.row", {}, h("h2", {}, "Connections"), h("span.spacer"),
      button("Re-check", (e) => busy(e.target, async () => { await api("/api/health/connections?fresh=1"); render(root.replaceChildren() || root); }), "sm")),
      c.error ? h("div.banner.warn", {}, c.error) : null,
      h("div.list", {}, c.accounts.map((a) => h("div", {}, h("span.pill." + (a.status === "ACTIVE" ? "ready" : a.status === "expired" ? "failed" : "warn"), {}, h("b", {}, a.status)),
        h("b", {}, a.label), h("span.muted.small.mono", {}, a.account), a.note ? h("span.small", { style: { color: "var(--bad)" } }, a.note) : null))),
      h("p.small.muted", {}, "Only the status is shown; keys stay on the server. 'expired' means Composio still lists the account but the last post failed with an invalidated token."));
  } catch (e) { conn.replaceChildren(h("h2", {}, "Connections"), h("div.banner.warn", {}, e.message)); }
}

function stat(label, value, kind) {
  return h("div.panel.stat", {}, h("span.muted.small", {}, label), h("b", { style: { color: kind === "bad" ? "var(--bad)" : kind === "warn" ? "var(--warn)" : "" } }, String(value)));
}
