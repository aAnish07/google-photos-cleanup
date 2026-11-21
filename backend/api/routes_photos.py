"""Photo listing, detail, and thumbnail serving."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from db import models
from db.database import get_db

router = APIRouter(prefix="/api/photos", tags=["photos"])


@router.get("")
async def list_photos(
    photo_type: Optional[str] = None,
    keep_signal: Optional[str] = None,
    has_text: Optional[str] = None,
    quality_signal: Optional[str] = None,
    classification_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    min_confidence: Optional[float] = None,
    trashed: Optional[str] = "false",
    sort: str = "created_time",
    order: str = "desc",
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> dict:
    params = {
        "photo_type": photo_type,
        "keep_signal": keep_signal,
        "has_text": has_text,
        "quality_signal": quality_signal,
        "classification_status": classification_status,
        "date_from": date_from,
        "date_to": date_to,
        "min_size": min_size,
        "max_size": max_size,
        "min_confidence": min_confidence,
        "trashed": trashed,
        "sort": sort,
        "order": order,
        "page": page,
        "per_page": per_page,
    }
    async with get_db() as db:
        return await models.query_photos(db, params)


@router.get("/{file_id}")
async def get_photo(file_id: str) -> dict:
    async with get_db() as db:
        photo = await models.get_photo(db, file_id)
    if not photo:
        raise HTTPException(404, "Photo not found.")
    return photo


@router.get("/{file_id}/image")
async def get_photo_image(file_id: str) -> FileResponse:
    async with get_db() as db:
        photo = await models.get_photo(db, file_id)
    if not photo or not photo.get("thumbnail_path"):
        raise HTTPException(404, "Thumbnail not available.")
    path = Path(photo["thumbnail_path"])
    if not path.exists():
        raise HTTPException(404, "Thumbnail file missing on disk.")
    return FileResponse(path, media_type="image/jpeg")
