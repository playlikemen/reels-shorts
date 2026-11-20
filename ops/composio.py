"""One Composio client for every ops script.

The consumer key is read from the COMPOSIO_CONSUMER_KEY environment variable, or from the
Composio MCP entry in ~/.claude.json. It is never written to the repo or printed.
"""
import json, os, re, subprocess, time

MCP_URL = "https://connect.composio.dev/mcp"


def _key():
    k = os.environ.get("COMPOSIO_CONSUMER_KEY")
    if k:
        return k
    path = os.path.expanduser("~/.claude.json")
    try:
        return json.load(open(path))["mcpServers"]["composio"]["headers"]["x-consumer-api-key"]
    except Exception:
        raise SystemExit("No Composio key: set COMPOSIO_CONSUMER_KEY or add the composio MCP server to ~/.claude.json")


def _call(tool, arguments, timeout=180):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
    # the key goes in through a curl config on stdin so it never shows up in the process list
    cfg = f'header = "x-consumer-api-key: {_key()}"\n'
    raw = subprocess.run(
        ["curl", "-sS", "-m", str(timeout), "-K", "-", "-X", "POST", MCP_URL,
         "-H", "content-type: application/json", "-H", "accept: application/json, text/event-stream", "-d", body],
        input=cfg, capture_output=True, text=True).stdout
    m = re.search(r"^data: (.*)$", raw, re.M)
    if not m:
        raise RuntimeError(f"Composio returned no data: {raw[:300]}")
    payload = json.loads(m.group(1))
    if "error" in payload:
        raise RuntimeError(f"Composio error: {json.dumps(payload['error'])[:300]}")
    text = payload.get("result", {}).get("content", [{}])[0].get("text", "{}")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def execute(slug, args, account, timeout=180):
    """Run one Composio tool on a named connected account. Returns the tool's `data`, raises on failure."""
    payload = {"sync_response_to_workbench": False, "tools": [{"tool_slug": slug, "account": account, "arguments": args}]}
    for attempt in range(4):
        res = _call("COMPOSIO_MULTI_EXECUTE_TOOL", payload, timeout)
        r = ((res.get("data") or {}).get("results") or [{}])[0]
        resp = r.get("response") or {}
        if not r.get("error") and resp.get("successful", False):
            if "data" not in resp and "data_preview" in resp:
                # Composio moved a large response to a remote file and sent only a preview. Never treat that as
                # empty: callers (sheet.rows) would then overwrite real rows.
                raise RuntimeError(f"{slug}: response too large, only a preview came back; request a smaller range")
            return resp.get("data") or {}
        err = str(r.get("error") or resp.get("error") or res)
        # per-minute rate limits (shared Google quota) clear on their own; daily quotas do not, so only short waits
        if "RATE_LIMIT_EXCEEDED" in err and "per minute" in err and attempt < 3:
            time.sleep(25 * (attempt + 1))
            continue
        raise RuntimeError(f"{slug} failed: {err[:400]}")


def proxy(toolkit, endpoint, method="GET", params=None, body=None, account=None, timeout=120):
    """Call the app's own REST API through the connected account. Returns {status, data, headers}."""
    args = {"toolkit_slug": toolkit, "endpoint": endpoint, "method": method}
    if params:
        args["parameters"] = [{"name": k, "value": str(v), "type": "query"} for k, v in params.items()]
    if body is not None:
        args["body"] = body
    if account:
        args["account"] = account
    res = _call("COMPOSIO_PROXY_EXECUTE", args, timeout)
    return res.get("data") or res


def stage_file(path, timeout=600):
    """Upload a local file to Composio's temporary storage and return its s3key.

    Tools that take a file (Drive upload, Instagram video_file, YouTube videoFile) accept
    {"name", "mimetype", "s3key"}. The slot is short-lived, so stage right before the call that uses it.
    """
    code = ('import os, requests, json\n'
            'r = requests.post(os.environ.get("BACKEND_URL","https://backend.composio.dev") + '
            '"/api/v3/tool_router/internal/presigned_url", json={"operation":"upload"})\n'
            'print("PRESIGN" + json.dumps(r.json()))')
    res = _call("COMPOSIO_REMOTE_WORKBENCH", {"code_to_execute": code})
    out = (res.get("data") or {}).get("stdout", "")
    m = re.search(r"PRESIGN(\{.*\})", out)
    if not m:
        raise RuntimeError(f"could not get an upload slot: {json.dumps(res)[:300]}")
    slot = json.loads(m.group(1))
    put = subprocess.run(["curl", "-sS", "-m", str(timeout), "-o", "/dev/null", "-w", "%{http_code}", "-X", "PUT",
                          "-H", "Content-Type: video/mp4", "--upload-file", str(path), slot["upload_url"]],
                         capture_output=True, text=True)
    if put.stdout.strip() != "200":
        raise RuntimeError(f"staging upload failed: HTTP {put.stdout.strip()} {put.stderr[:200]}")
    return slot["key"]


def file_arg(path):
    return {"name": os.path.basename(str(path)), "mimetype": "video/mp4", "s3key": stage_file(path)}
