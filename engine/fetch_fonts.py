"""Download the Google Fonts used by the templates into ./fonts and write fonts.css (offline, deterministic renders)."""
import re, urllib.request, pathlib, sys
HERE = pathlib.Path(__file__).parent
FAMILIES = [
    "Anton", "Archivo:wght@500;700;800;900", "JetBrains+Mono:wght@500;700;800",
    "Instrument+Serif", "Inter:wght@400;500;600;700;800", "Space+Grotesk:wght@500;700",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()
out_css = []
fdir = HERE / "fonts"; fdir.mkdir(exist_ok=True)
for fam in FAMILIES:
    css = get(f"https://fonts.googleapis.com/css2?family={fam}&display=block").decode()
    for block in re.findall(r"/\* ([^*]+) \*/\s*(@font-face \{.*?\})", css, re.S):
        subset, face = block
        if subset.strip() not in ("latin",):   # keep latin only (small, enough for English)
            continue
        url = re.search(r"url\((https://[^)]+)\)", face).group(1)
        name = re.sub(r"[^a-z0-9]+", "-", (re.search(r"font-family: '([^']+)'", face).group(1) + "-" +
               re.search(r"font-weight: (\d+)", face).group(1)).lower()) + ".woff2"
        (fdir / name).write_bytes(get(url))
        out_css.append(face.replace(url, f"fonts/{name}"))
(HERE / "fonts.css").write_text("\n".join(out_css))
print("fonts:", len(out_css), "faces ->", fdir)
