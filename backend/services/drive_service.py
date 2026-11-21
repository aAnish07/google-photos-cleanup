"""Google Drive access: list image files, download thumbnails, trash/untrash.

The Google API client is synchronous, so blocking calls are run in a thread via
`asyncio.to_thread`. A small async rate limiter keeps us within Drive quotas.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from auth.google_oauth import load_credentials
from config import DRIVE_LIST_RPS, DRIVE_PAGE_SIZE, DRIVE_TRASH_RPS

# Drive query: images only (video support can be added by widening this).
IMAGE_QUERY = "(mimeType contains 'image/') and trashed = false and 'me' in owners"
FILE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, size, createdTime, "
    "modifiedTime, thumbnailLink, webViewLink)"
)


class _RateLimiter:
    """Simple async rate limiter: at most `rps` acquisitions per second."""

    def __init__(self, rps: float) -> None:
        self._min_interval = 1.0 / rps if rps > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._min_interval - (now - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


_list_limiter = _RateLimiter(DRIVE_LIST_RPS)
_trash_limiter = _RateLimiter(DRIVE_TRASH_RPS)


def _service():
    """Build a Drive v3 service from stored credentials (runs in a thread)."""
    creds = load_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _normalize(file: dict[str, Any]) -> dict[str, Any]:
    size = file.get("size")
    return {
        "id": file["id"],
        "name": file.get("name"),
        "mime_type": file.get("mimeType"),
        "size_bytes": int(size) if size is not None else None,
        "created_time": file.get("createdTime"),
        "modified_time": file.get("modifiedTime"),
        "thumbnail_url": file.get("thumbnailLink"),
        "web_view_link": file.get("webViewLink"),
    }


async def list_image_files(
    page_token: Optional[str] = None, page_size: int = DRIVE_PAGE_SIZE
) -> dict[str, Any]:
    """List one page of image files, newest first."""
    await _list_limiter.wait()

    def _call() -> dict[str, Any]:
        service = _service()
        return (
            service.files()
            .list(
                q=IMAGE_QUERY,
                fields=FILE_FIELDS,
                pageSize=page_size,
                orderBy="createdTime desc",
                pageToken=page_token,
                spaces="drive",
            )
            .execute()
        )

    resp = await asyncio.to_thread(_call)
    return {
        "files": [_normalize(f) for f in resp.get("files", [])],
        "next_page_token": resp.get("nextPageToken"),
    }


async def count_image_files() -> dict[str, int]:
    """Page through all image files to get an exact count and total size."""
    total, total_size, token = 0, 0, None
    while True:
        page = await list_image_files(page_token=token, page_size=1000)
        for f in page["files"]:
            total += 1
            total_size += f["size_bytes"] or 0
        token = page["next_page_token"]
        if not token:
            break
    return {"count": total, "total_size_bytes": total_size}


async def download_thumbnail(
    file_id: str, thumbnail_url: str, save_dir: str, size_px: int = 1600
) -> str:
    """Download a Drive thumbnail (authenticated) and save it locally as-is.

    Image preparation for Jev (resize/pad/EXIF) happens in the classifier, not
    here. Returns the local file path.
    """
    creds = await asyncio.to_thread(load_credentials)
    # thumbnailLink accepts a size suffix; request a generous size for quality.
    url = thumbnail_url
    if "=s" in url:
        url = url.rsplit("=s", 1)[0] + f"=s{size_px}"

    Path(save_dir).mkdir(parents=True, exist_ok=True)
    dest = Path(save_dir) / f"{file_id}.jpg"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {creds.token}"})
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return str(dest)


async def _set_trashed(file_ids: list[str], trashed: bool) -> dict[str, list]:
    succeeded, failed = [], []

    def _update(fid: str) -> None:
        service = _service()
        service.files().update(
            fileId=fid, body={"trashed": trashed}, fields="id"
        ).execute()

    for fid in file_ids:
        await _trash_limiter.wait()
        try:
            await asyncio.to_thread(_update, fid)
            succeeded.append(fid)
        except HttpError as exc:
            failed.append({"id": fid, "error": str(exc)})
        except Exception as exc:  # network, auth, etc.
            failed.append({"id": fid, "error": str(exc)})
    return {"succeeded": succeeded, "failed": failed}


async def trash_files(file_ids: list[str]) -> dict[str, list]:
    return await _set_trashed(file_ids, True)


async def untrash_files(file_ids: list[str]) -> dict[str, list]:
    return await _set_trashed(file_ids, False)
