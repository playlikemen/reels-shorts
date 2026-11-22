// Settings: channels (auto-publish, slots, daily cap), MCP key, import from the Sheet, password, API tokens for agents.
import { h, api, post, button, busy, toast, modal, state, brandDot, reloadBrands, jobToast } from "../app.js";

function channelsPanel() {
  const panel = h("div#channels.panel", {}, h("h2", {}, "Channels"),
    h("p.small.muted", {}, "Auto-publish is the master switch for cron posting. Off: cron posts nothing for that channel; Publish now still works. Slots and the daily cap drive “Next free slot” and the scheduler. Every change is in the audit log."));
  const list = h("div.chlist");
  const draw = () => list.replaceChildren(...state.brands.map((b) => {
    const auto = h("input", { type: "checkbox", role: "switch", checked: b.auto_publish !== false, "aria-label": `Auto-publish ${b.name}` });
    const yt = b.youtube ? h("input", { type: "checkbox", role: "switch", checked: b.youtube_auto !== false, "aria-label": `YouTube auto-upload ${b.name}` }) : null;
    const slots = h("input", { value: (b.slots || []).join(", "), placeholder: "12:30, 19:30", "aria-label": `Slots ${b.name}`, size: 14 });
    const cap = h("input", { type: "number", min: 1, max: 20, value: b.cap ?? "", placeholder: "none", "aria-label": `Daily cap ${b.name}`, style: { width: "72px" } });
    const save = button("Save", (e) => busy(e.target, async () => {
      const body = { brand: b.key, auto_publish: auto.checked, slots: slots.value.split(/[,\s]+/).filter(Boolean), cap: cap.value ? +cap.value : null };
      if (yt) body.youtube_auto = yt.checked;
      await post("/api/channels", body);
      await reloadBrands();
      toast(`${b.name} saved${auto.checked ? "" : " · auto-publish is OFF"}`, auto.checked ? "ok" : "error");
      draw();
    }), "sm primary");
    return h("div.chrow", { id: `ch-${b.key}` },
      h("div.chname", {}, brandDot(b.key), h("b", {}, b.name), h("span.small.muted", {}, b.instagram), b.youtube ? h("span.small.muted", {}, ` · ${b.youtube}`) : null),
      h("label.check", {}, auto, h("span", {}, "Auto-publish")),
      yt ? h("label.check", {}, yt, h("span", {}, "YouTube auto-upload")) : h("span.small.muted", {}, "no YouTube"),
      h("label.field.inline", {}, "Slots (IST)", slots), h("label.field.inline", {}, "Per day", cap), save);
  }));
  draw();
  panel.append(list, h("div.row", { style: { marginTop: "12px" } },
    button("Move published Drive folders into Published/", (e) => busy(e.target, async () => {
      const r = await post("/api/jobs", { kind: "backfill" }); jobToast(r.job, "Drive backfill");
    }), "sm"), h("span.small.muted", {}, "One-off. New posts are moved there automatically; nothing is deleted.")));
  return panel;
}

// MCP server: the endpoint, the one owner key (shown once on rotate; only its hash is stored), revoke.
function mcpPanel() {
  const url = `${location.origin}/mcp`;
  const info = h("p.small");
  const shown = h("div");
  const load = async () => {
    const k = await api("/api/settings/mcp-key");
    info.replaceChildren(k.set ? `Key set ${new Date(k.created * 1000).toLocaleString()}.` : "No key set: MCP clients get the read-only tools only.");
  };
  load();
  return h("div#mcp.panel", {}, h("h2", {}, "MCP server"),
    h("p.small.muted", {}, "AI agents and apps (Composio, Claude, the MCP inspector) connect to this URL. Without the key they can only read, and private links stay hidden. With the key they can do everything the studio can, including publishing (publish tools need confirm: true)."),
    h("div.row", {}, h("code.mono", {}, url), button("Copy", () => navigator.clipboard.writeText(url).then(() => toast("Copied", "ok")), "sm ghost")),
    h("p.small.muted", {}, "Send the key as Authorization: Bearer <key>, or X-API-Key: <key>, or ?api_key=<key> in the URL."),
    info, shown,
    h("div.row", { style: { marginTop: "10px" } },
      button("Rotate key", (e) => busy(e.target, async () => {
        if (!confirm("Make a new key? The old key stops working at once, so update every MCP client.")) return;
        const r = await post("/api/settings/mcp-key/rotate", {});
        const box = h("input.mono", { value: r.key, readonly: true, style: { width: "100%" }, onclick: (ev) => ev.target.select() });
        shown.replaceChildren(h("div.banner.warn", {}, h("div", {}, h("b", {}, "New key, shown once: "), box,
          button("Copy key", () => navigator.clipboard.writeText(r.key).then(() => toast("Key copied", "ok")), "sm"))));
        load();
      }), "sm"),
      button("Revoke key", (e) => busy(e.target, async () => {
        if (!confirm("Revoke the key? MCP clients drop to read-only at once.")) return;
        await post("/api/settings/mcp-key/revoke", {}); shown.replaceChildren(); toast("Key revoked", "ok"); load();
      }), "sm danger")));
}

// Import from the Sheet: recovery only. Shows what differs and applies only the ticked cells and rows.
function importPanel() {
  const tab = h("select", { "aria-label": "Tab" }, state.brands.map((b) => h("option", { value: b.tab }, `${b.name} (${b.tab})`)));
  const out = h("div");
  const compare = button("Compare with the Sheet", (e) => busy(e.target, async () => {
    const d = (await api(`/api/import/preview?tab=${encodeURIComponent(tab.value)}`)).diff[tab.value];
    if (!d || d.error) { out.replaceChildren(h("div.banner.bad", {}, d?.error || "could not read the tab")); return; }
    const boxes = [];
    const cell = (vid, k, c) => { const cb = h("input", { type: "checkbox", dataset: { vid, k } }); boxes.push(cb);
      return h("tr", {}, h("td", {}, cb), h("td", {}, h("b", {}, vid)), h("td", {}, k), h("td", {}, h("div.preview", {}, c.studio || "—")), h("td", {}, h("div.preview", {}, c.sheet || "—"))); };
    const rowsNew = d.new.map((x) => { const cb = h("input", { type: "checkbox", dataset: { newid: x["Video ID"] } }); boxes.push(cb);
      return h("label.check", {}, cb, h("span", {}, h("b", {}, x["Video ID"]), ` ${x["Category / Topic"]} · ${x["Instagram Status"]}`)); });
    const cells = Object.entries(d.changed).flatMap(([vid, cs]) => Object.entries(cs).map(([k, c]) => cell(vid, k, c)));
    const apply = button("Apply ticked", (ev) => busy(ev.target, async () => {
      const changes = {}, nw = [];
      boxes.filter((b) => b.checked).forEach((b) => { if (b.dataset.newid) nw.push(b.dataset.newid); else (changes[b.dataset.vid] ||= []).push(b.dataset.k); });
      const r = await post("/api/import/apply", { tab: tab.value, changes, new: nw });
      toast(`Imported ${r.applied.cells} cell(s) and ${r.applied.rows} row(s) from the Sheet`, "ok"); compare.click();
    }), "primary sm");
    out.replaceChildren(
      h("p.small.muted", {}, `Sheet ${d.sheet_rows} rows · studio ${d.studio_rows} rows · ${cells.length} cell(s) differ · ${d.new.length} row(s) only in the Sheet · ${d.only_in_studio.length} only in the studio (they are mirrored on the next push).`),
      cells.length ? h("div.tbl-wrap", {}, h("table.tbl", {}, h("thead", {}, h("tr", {}, ["", "ID", "Cell", "Studio (kept unless ticked)", "Sheet"].map((t) => h("th", {}, t)))), h("tbody", {}, cells))) : null,
      rowsNew.length ? [h("h3", { style: { margin: "12px 0 6px" } }, "Rows only in the Sheet"), rowsNew] : null,
      cells.length || rowsNew.length ? h("div.row", { style: { marginTop: "10px" } }, apply) : h("p", {}, "The studio and the Sheet match."));
  }), "sm");
  return h("div#import.panel", {}, h("h2", {}, "Import from Sheet"),
    h("p.small.muted", {}, "The studio is the source of truth and the Sheet is a read-only mirror for other agents. Use this only to recover something that was typed into the Sheet: nothing is applied unless you tick it."),
    h("div.row", {}, tab, compare), out);
}

export async function render(root) {
  const cur = h("input", { type: "password", autocomplete: "current-password" });
  const nw = h("input", { type: "password", autocomplete: "new-password", minlength: 10 });
  const s = await api("/api/session");
  const tokens = h("div.list");
  const name = h("input", { placeholder: "agent-name" });
  const loadTokens = async () => {
    const t = await api("/api/settings/tokens");
    tokens.replaceChildren(...(t.tokens.length ? t.tokens.map((x) => h("div", {}, h("b", {}, x.name), h("span.muted.small", {}, new Date(x.created * 1000).toLocaleString()), h("span.spacer"),
      button("Revoke", (e) => busy(e.target, async () => { await post("/api/settings/tokens/revoke", { name: x.name }); loadTokens(); }), "sm danger"))) : [h("p.muted", {}, "No tokens.")]));
  };
  root.append(h("header.page", {}, h("h1", {}, "Settings")), channelsPanel(), mcpPanel(), importPanel(),
    s.has_initial_password_file ? h("div.banner.warn", {}, "The generated first password is still stored in ~/.config/reels-studio/initial-password.txt. Change the password below (that removes the file) or delete it by hand.") : null,
    h("div.grid2", {},
      h("div.panel", {}, h("h2", {}, "Change password"), h("div", { style: { display: "grid", gap: "10px" } },
        h("label.field", {}, "Current password", cur), h("label.field", {}, "New password (10+ characters)", nw),
        button("Change password", (e) => busy(e.target, async () => {
          await post("/api/settings/password", { current: cur.value, new: nw.value }); toast("Password changed; log in again", "ok"); setTimeout(() => (location.href = "/login"), 1200);
        }), "primary"), h("p.small.muted", {}, "Changing it signs every session out."))),
      h("div.panel", {}, h("h2", {}, "API tokens (for agents)"),
        h("p.small.muted", {}, "Send as Authorization: Bearer <token>. Token requests need no CSRF header. Every call is in the audit log under token:<name>."),
        tokens, h("div.row", { style: { marginTop: "10px" } }, name, button("Create", (e) => busy(e.target, async () => {
          const t = await post("/api/settings/tokens", { name: name.value.trim() });
          modal("New API token", [h("p", {}, "Copy it now; it is not shown again."), h("pre.log", {}, t.token)]); loadTokens();
        }), "primary")))),
    h("div.panel", {}, h("h2", {}, "Extra protection"), h("p.small", {}, "The public hostname can also sit behind Cloudflare Access (email one-time codes): Zero Trust → Access → Applications → Self-hosted → the studio hostname. The studio password still applies after it.")));
  loadTokens();
}
