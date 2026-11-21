try { const t = localStorage.getItem("rs-theme"); if (t) document.documentElement.dataset.theme = t; } catch { /* */ }
const form = document.getElementById("login"), err = document.getElementById("err"), go = document.getElementById("go");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  err.textContent = ""; go.disabled = true; go.classList.add("loading");
  try {
    const r = await fetch("/api/login", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ password: document.getElementById("pw").value }), credentials: "same-origin" });
    const d = await r.json().catch(() => ({}));
    if (r.ok) { location.href = "/" + (location.hash || ""); return; }
    err.textContent = d.error || `HTTP ${r.status}`;
  } catch (x) { err.textContent = x.message; }
  go.disabled = false; go.classList.remove("loading");
});
