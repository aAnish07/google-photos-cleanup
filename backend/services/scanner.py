"""Scan orchestrator: Drive listing -> thumbnail -> classify -> store.

Resumable (via scan_runs.next_page_token) and cancellable. Designed to run as
a FastAPI background task. Only one scan runs at a time.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from config import THUMBNAIL_CONCURRENCY, THUMBNAIL_DIR
from db import models
from db.database import get_db
from services import drive_service
from services.classifier import get_classifier

logger = logging.getLogger("scanner")

# Cancellation + single-run coordination (process-local).
_cancelled: set[str] = set()
_running_lock = asyncio.Lock()
_running_scan_id: Optional[str] = None


def request_cancel(scan_id: str) -> None:
    _cancelled.add(scan_id)


def is_running() -> bool:
    return _running_scan_id is not None


def current_scan_id() -> Optional[str]:
    return _running_scan_id


async def run_scan(scan_id: str, resume_page_token: Optional[str] = None) -> None:
    """Run (or resume) a scan. Safe to call as a background task."""
    global _running_scan_id

    if _running_lock.locked():
        logger.warning("A scan is already running; ignoring scan %s", scan_id)
        return

    async with _running_lock:
        _running_scan_id = scan_id
        _cancelled.discard(scan_id)
        classifier = get_classifier()
        page_token = resume_page_token
        try:
            async with get_db() as db:
                if await models.get_scan_run(db, scan_id) is None:
                    await models.create_scan_run(db, scan_id)
                    await db.commit()

            while True:
                if scan_id in _cancelled:
                    await _finish(scan_id, "cancelled")
                    return

                page = await drive_service.list_image_files(page_token=page_token)
                files = page["files"]
                page_token = page["next_page_token"]

                await _process_page(scan_id, files, classifier)

                async with get_db() as db:
                    await models.update_scan_progress(
                        db, scan_id, next_page_token=page_token or ""
                    )
                    await db.commit()

                if not page_token:
                    break

            await _finish(scan_id, "completed")
        except Exception:
            logger.exception("Scan %s failed", scan_id)
            await _finish(scan_id, "failed")
        finally:
            _running_scan_id = None
            await _aclose(classifier)


async def _process_page(scan_id: str, files: list[dict], classifier) -> None:
    if not files:
        return

    # Skip files already known.
    async with get_db() as db:
        known = await models.existing_ids(db, [f["id"] for f in files])
        new_files = [f for f in files if f["id"] not in known]
        for f in new_files:
            await models.insert_photo_metadata(db, f, scan_batch=scan_id)
        await models.update_scan_progress(db, scan_id, total_files=len(new_files))
        await db.commit()

    if not new_files:
        return

    sem = asyncio.Semaphore(THUMBNAIL_CONCURRENCY)

    async def handle(f: dict) -> tuple[bool, bool]:
        """Return (classified_ok, failed)."""
        async with sem:
            try:
                thumb = await drive_service.download_thumbnail(
                    f["id"], f["thumbnail_url"], str(THUMBNAIL_DIR)
                )
            except Exception as exc:
                await _record_failure(f["id"], f"thumbnail: {exc}")
                return (False, True)

            async with get_db() as db:
                await models.set_thumbnail_path(db, f["id"], thumb)
                await db.commit()

            try:
                result = await classifier.classify_image(thumb)
            except Exception as exc:
                await _record_failure(f["id"], f"classify: {exc}")
                return (False, True)

            async with get_db() as db:
                await models.save_classification(db, f["id"], result)
                await db.commit()
            return (True, False)

    results = await asyncio.gather(*(handle(f) for f in new_files))
    classified = sum(1 for ok, _ in results if ok)
    failed = sum(1 for _, bad in results if bad)

    async with get_db() as db:
        await models.update_scan_progress(
            db, scan_id, classified=classified, failed=failed
        )
        await db.commit()


async def _record_failure(file_id: str, error: str) -> None:
    async with get_db() as db:
        await models.mark_classification_failed(db, file_id, error)
        await db.commit()


async def _finish(scan_id: str, status: str) -> None:
    async with get_db() as db:
        await models.finish_scan_run(db, scan_id, status)
        await db.commit()


async def _aclose(classifier) -> None:
    close = getattr(classifier, "aclose", None)
    if close is not None:
        try:
            await close()
        except Exception:
            pass
