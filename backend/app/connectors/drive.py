from __future__ import annotations

from pathlib import Path
from typing import Any

from . import google_auth


def live() -> bool:
    return google_auth.connected()


def _service():
    return google_auth.google_service("drive", "v3")


def upload_file(path: str | Path, title: str = "") -> dict[str, Any]:
    from googleapiclient.http import MediaFileUpload

    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(str(file_path))
    name = title or file_path.name
    media = MediaFileUpload(str(file_path), resumable=False)
    created = (
        _service()
        .files()
        .create(body={"name": name}, media_body=media, fields="id,name,webViewLink,webContentLink")
        .execute()
    )
    file_id = created.get("id") or ""
    link = created.get("webViewLink") or ""
    if file_id and not link:
        link = f"https://drive.google.com/file/d/{file_id}/view"
    return {
        "id": file_id,
        "name": created.get("name") or name,
        "title": Path(created.get("name") or name).stem,
        "link": link,
        "kind": "drive",
    }


def find_by_title(title: str, limit: int = 5) -> list[dict[str, Any]]:
    safe = (title or "").replace("'", "\\'")
    if not safe:
        return []
    listed = (
        _service()
        .files()
        .list(
            q=f"name contains '{safe}' and trashed = false",
            pageSize=limit,
            fields="files(id,name,webViewLink)",
        )
        .execute()
    )
    rows = []
    for item in listed.get("files") or []:
        file_id = item.get("id") or ""
        link = item.get("webViewLink") or (f"https://drive.google.com/file/d/{file_id}/view" if file_id else "")
        rows.append(
            {
                "id": file_id,
                "name": item.get("name") or "",
                "title": Path(item.get("name") or "").stem,
                "link": link,
                "kind": "drive",
            }
        )
    return rows
