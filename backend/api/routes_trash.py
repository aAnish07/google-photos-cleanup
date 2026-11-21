"""Trash / undo routes. Trash-only (never permanent delete); 30-day recovery.

A trash-by-filter call is a two-step confirm: first POST returns a count and a
confirmation token; the client echoes the token to actually trash.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import models
from db.database import get_db
from services import drive_service

router = APIRouter(prefix="/api/trash", tags=["trash"])


class FileIds(BaseModel):
    file_ids: list[str]


class FilterTrash(BaseModel):
    # Mirrors the GET /api/photos filter params.
    photo_type: Optional[str] = None
    keep_signal: Optional[str] = None
    has_text: Optional[str] = None
    quality_signal: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    min_confidence: Optional[float] = None
    confirm_token: Optional[str] = None


def _token_for(ids: list[str]) -> str:
    h = hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest()
    return h[:16]


@router.post("")
async def trash(payload: FileIds) -> dict:
    if not payload.file_ids:
        raise HTTPException(400, "No file_ids provided.")
    result = await drive_service.trash_files(payload.file_ids)
    succeeded = result["succeeded"]
    async with get_db() as db:
        await models.set_trashed(db, succeeded, True)
        if succeeded:
            await models.record_trash_batch(
                db, f"batch_{uuid.uuid4().hex[:12]}", "trash", succeeded
            )
        await db.commit()
    return result


@router.post("/undo")
async def undo(payload: Optional[FileIds] = None) -> dict:
    """Untrash the given ids, or the most recent trash batch if none given."""
    file_ids = payload.file_ids if payload and payload.file_ids else None
    if file_ids is None:
        async with get_db() as db:
            last = await models.latest_trash_batch(db)
        if not last:
            raise HTTPException(404, "No trash batch to undo.")
        file_ids = last["file_ids"]

    result = await drive_service.untrash_files(file_ids)
    succeeded = result["succeeded"]
    async with get_db() as db:
        await models.set_trashed(db, succeeded, False)
        if succeeded:
            await models.record_trash_batch(
                db, f"batch_{uuid.uuid4().hex[:12]}", "untrash", succeeded
            )
        await db.commit()
    return result


@router.post("/by-filter")
async def trash_by_filter(payload: FilterTrash) -> dict:
    params = payload.model_dump()
    confirm_token = params.pop("confirm_token")
    params["trashed"] = "false"

    async with get_db() as db:
        ids = await models.ids_matching_filter(db, params)

    if not ids:
        return {"count": 0, "succeeded": [], "failed": []}

    expected = _token_for(ids)
    if confirm_token != expected:
        # First pass: tell the client how many match and hand back the token.
        async with get_db() as db:
            size_rows = [await models.get_photo(db, i) for i in ids]
        total_size = sum((p or {}).get("size_bytes") or 0 for p in size_rows)
        return {
            "requires_confirmation": True,
            "count": len(ids),
            "total_size_bytes": total_size,
            "confirm_token": expected,
        }

    # Confirmed: trash them.
    result = await drive_service.trash_files(ids)
    succeeded = result["succeeded"]
    async with get_db() as db:
        await models.set_trashed(db, succeeded, True)
        if succeeded:
            await models.record_trash_batch(
                db, f"batch_{uuid.uuid4().hex[:12]}", "trash", succeeded
            )
        await db.commit()
    return {"count": len(ids), **result}
