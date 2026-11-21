// Settings: password, API tokens for agents, theme.
import { h, api, post, button, busy, toast, modal } from "../app.js";

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
  root.append(h("header.page", {}, h("h1", {}, "Settings")),
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
