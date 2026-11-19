"""Archive a finished MP4 in the shared Google Drive folder and return its links."""
import os, sys
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
