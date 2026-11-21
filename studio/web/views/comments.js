// Comments inbox: latest comments on each brand's recent reels; a keyword badge when a comment matches the reel's
// CTA keyword. Replies go out only when Send is clicked.
import { h, api, post, state, button, busy, toast, ago, short } from "../app.js";

const ui = { brand: "" };

export async function render(root) {
  ui.brand = ui.brand || state.brands[0]?.key || "";
  const body = h("div");
  const brand = h("select", { onchange: (e) => { ui.brand = e.target.value; load(); } }, state.brands.map((b) => h("option", { value: b.key, selected: ui.brand === b.key }, `${b.name} ${b.instagram}`)));
  const refresh = button("Refresh from Instagram", (e) => busy(e.target, async () => {
    try { await post("/api/comments/refresh", { brand: ui.brand }); } catch (x) { body.prepend(h("div.banner.bad", {}, x.message)); return; }
    load();
  }), "primary");
  root.append(h("header.page", {}, h("h1", {}, "Comments"), brand, refresh, h("div.sub", {}, "Reply within the first hour. A green card means the comment has the reel's CTA keyword.")), body);
  async function load() {
    const d = await api(`/api/comments?brand=${ui.brand}`);
    if (!d.media.length) { body.replaceChildren(h("div.empty", {}, h("h2", {}, d.fetched_at ? "No reels found" : "Not loaded yet"), h("p", {}, "Press Refresh. It reads the 8 latest reels and their comments."))); return; }
    const hits = d.media.flatMap((m) => m.comments.filter((c) => c.keyword_hit && !c.replies)).length;
    body.replaceChildren(
      h("p.small.muted", {}, `Fetched ${ago(d.fetched_at)}${hits ? ` · ${hits} keyword comment(s) without a reply` : ""}`),
      ...d.media.map((m) => h("section.panel", {},
        h("div.row", { style: { marginBottom: "10px" } }, h("h2", {}, m.video_id || "Reel"), m.keyword ? h("span.pill.published", {}, "keyword ", h("b", {}, m.keyword)) : null,
          h("span.muted.small", {}, `${m.posted?.slice(0, 10) || ""} · ${m.comments.length} comment(s)`), h("span.spacer"), h("a", { href: m.permalink, target: "_blank", rel: "noopener" }, "Open ↗")),
        h("p.small.muted", {}, short(m.caption, 140)),
        m.error ? h("div.banner.warn", {}, `Could not read comments: ${m.error}`) : null,
        h("div.cmedia", {}, m.comments.length ? m.comments.map((c) => comment(c, m)) : h("p.small.muted", {}, "No comments yet.")))));
  }
  await load();
}

function comment(c, m) {
  const input = h("input", { placeholder: `Reply to @${c.username}…`, maxlength: 300 });
  const send = button("Send", (e) => busy(e.target, async () => {
    if (!input.value.trim()) return;
    await post("/api/comments/reply", { brand: ui.brand, comment_id: c.id, message: input.value, send: true });
    toast(`Replied to @${c.username}`, "ok"); input.value = ""; input.disabled = true; e.target.remove();
  }), "sm primary");
  return h("div.comment", { class: c.keyword_hit ? "hit" : "" },
    h("div.who", {}, `@${c.username}`, c.keyword_hit ? h("span.pill.ready", {}, h("b", {}, m.keyword)) : null, c.replies ? h("span.pill", {}, `${c.replies} repl${c.replies > 1 ? "ies" : "y"}`) : null,
      h("span.muted.small", {}, ago(c.timestamp))),
    h("div", {}, c.text),
    h("div.reply", {}, input, send));
}
