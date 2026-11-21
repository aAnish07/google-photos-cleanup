"""Scan control routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from db import models
from db.database import get_db
from services import drive_service, scanner

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.post("/start")
async def start_scan(background: BackgroundTasks) -> dict:
    if scanner.is_running():
        raise HTTPException(409, "A scan is already running.")

    # Resume an interrupted run if one has a saved page token; else start fresh.
    resume_token = None
    scan_id = None
    async with get_db() as db:
        latest = await models.latest_scan_run(db)
        if latest and latest["status"] == "running" and latest["next_page_token"]:
            scan_id = latest["id"]
            resume_token = latest["next_page_token"] or None

    if scan_id is None:
        scan_id = f"scan_{uuid.uuid4().hex[:12]}"

    background.add_task(scanner.run_scan, scan_id, resume_token)
    return {"scan_id": scan_id, "resumed": resume_token is not None}


@router.get("/status")
async def scan_status() -> dict:
    async with get_db() as db:
        latest = await models.latest_scan_run(db)
    return {
        "running": scanner.is_running(),
        "current_scan_id": scanner.current_scan_id(),
        "latest": latest,
    }


@router.post("/cancel")
async def cancel_scan() -> dict:
    sid = scanner.current_scan_id()
    if not sid:
        raise HTTPException(404, "No scan is currently running.")
    scanner.request_cancel(sid)
    return {"cancelling": sid}


@router.get("/library-size")
async def library_size() -> dict:
    """Exact count + total size of image files in Drive (no classification)."""
    return await drive_service.count_image_files()
