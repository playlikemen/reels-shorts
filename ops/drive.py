"""Archive a finished MP4 in the shared Google Drive folder and return its links."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import composio as C
import config as K


def archive(folder_name, mp4):
    size = os.path.getsize(mp4)
    if size < K.MIN_MP4_BYTES:
        raise ValueError(f"{mp4} is {size} bytes; refusing to upload anything under 100 KB")
    folder = C.execute("GOOGLEDRIVE_CREATE_FOLDER", {"name": folder_name, "parent_id": K.DRIVE_PARENT}, K.DRIVE_ACCOUNT)
    folder_id = folder.get("id") or (folder.get("file") or {}).get("id")
    if not folder_id:
        raise RuntimeError(f"Drive folder not created: {folder}")
    up = C.execute("GOOGLEDRIVE_UPLOAD_FILE", {"file_to_upload": C.file_arg(mp4), "folder_to_upload_to": folder_id}, K.DRIVE_ACCOUNT, timeout=600)
    file_id = up.get("id") or (up.get("file") or {}).get("id")
    if not file_id:
        raise RuntimeError(f"Drive upload returned no file id: {str(up)[:300]}")
    meta = C.execute("GOOGLEDRIVE_GET_FILE_METADATA", {"file_id": file_id, "fields": "id,name,size,parents"}, K.DRIVE_ACCOUNT)
    if int(meta.get("size", 0)) != size:
        raise RuntimeError(f"Drive size {meta.get('size')} differs from local size {size}")
    if folder_id not in (meta.get("parents") or []):
        raise RuntimeError("Drive put the file outside the reel folder")
    for fid in (file_id, folder_id):
        C.execute("GOOGLEDRIVE_CREATE_PERMISSION", {"file_id": fid, "type": "anyone", "role": "reader"}, K.DRIVE_ACCOUNT)
    return {"folder_id": folder_id, "folder_link": f"https://drive.google.com/drive/folders/{folder_id}",
            "file_id": file_id, "direct_link": f"https://drive.google.com/uc?id={file_id}&export=download"}


# ---------- subfolders: Published/ and Archive/ under DRIVE_PARENT ----------

FOLDER_MIME = "application/vnd.google-apps.folder"
FOLDER_RE = re.compile(r"/folders/([\w-]{10,})")


def folder_id(link):
    """The folder id in a 'Google Drive Folder' cell (https://drive.google.com/drive/folders/<id>), or ''."""
    m = FOLDER_RE.search(link or "")
    return m.group(1) if m else ""


def _subs_path():
    return K.STATE / "drive_subfolders.json"


def ensure_sub(name):
    """Id of the subfolder `name` directly under DRIVE_PARENT, created once and remembered in the state dir."""
    if name not in ("Published", "Archive"):
        raise ValueError("only the Published and Archive subfolders are used")
    try:
        cache = json.loads(_subs_path().read_text())
    except (OSError, ValueError):
        cache = {}
    if cache.get(name):
        return cache[name]
    q = f"name = '{name}' and mimeType = '{FOLDER_MIME}' and '{K.DRIVE_PARENT}' in parents and trashed = false"
    found = C.execute("GOOGLEDRIVE_FIND_FILE", {"q": q, "pageSize": 5, "fields": "files(id,name)"}, K.DRIVE_ACCOUNT)
    files = found.get("files") or []
    fid = files[0]["id"] if files else ""
    if not fid:
        made = C.execute("GOOGLEDRIVE_CREATE_FOLDER", {"name": name, "parent_id": K.DRIVE_PARENT}, K.DRIVE_ACCOUNT)
        fid = made.get("id") or (made.get("file") or {}).get("id")
        if not fid:
            raise RuntimeError(f"Drive folder {name} not created: {str(made)[:200]}")
    cache[name] = fid
    _subs_path().write_text(json.dumps(cache))
    return fid


def move(folder, sub):
    """Move a reel's Drive folder (id or folder link) into Published/ or Archive/, or back to DRIVE_PARENT (sub='').
    Only moves; nothing is ever deleted. Returns the destination folder id."""
    fid = folder_id(folder) or folder
    if not re.match(r"^[\w-]{10,}$", fid or ""):
        raise ValueError("no Drive folder id")
    dest = ensure_sub(sub) if sub else K.DRIVE_PARENT
    C.execute("GOOGLEDRIVE_MOVE_FILE", {"file_id": fid, "add_parents": dest}, K.DRIVE_ACCOUNT)
    return dest
