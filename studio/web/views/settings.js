// Settings: channels (auto-publish, slots, daily cap), password, API tokens for agents.
import { h, api, post, button, busy, toast, modal, state, brandDot, reloadBrands } from "../app.js";

function channelsPanel() {
  const panel = h("div.panel#channels", {}, h("h2", {}, "Channels"),
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
  panel.append(list);
  return panel;
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
  root.append(h("header.page", {}, h("h1", {}, "Settings")), channelsPanel(),
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
