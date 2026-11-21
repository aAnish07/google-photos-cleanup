"""Aggregate stats route."""
from __future__ import annotations

from fastapi import APIRouter

from db import models
from db.database import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def stats() -> dict:
    async with get_db() as db:
        return await models.get_stats(db)
