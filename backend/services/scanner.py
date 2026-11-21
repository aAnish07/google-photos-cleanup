"""Scan orchestrator: Drive listing -> thumbnail/frames -> classify -> store.

Handles both images (classify the thumbnail) and videos (sample frames,
classify each, aggregate). Resumable (via scan_runs.next_page_token) and
cancellable. Designed to run as a FastAPI background task; one scan at a time.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from config import (
    INCLUDE_VIDEOS,
    MAX_VIDEO_BYTES,
    THUMBNAIL_CONCURRENCY,
    THUMBNAIL_DIR,
    VIDEO_CONCURRENCY,
    VIDEO_FRAMES,
)
from db import models
from db.database import get_db
from services import drive_service, video_service
from services.classifier import get_classifier

logger = logging.getLogger("scanner")

_cancelled: set[str] = set()
_running_lock = asyncio.Lock()
_running_scan_id: Optional[str] = None


def request_cancel(scan_id: str) -> None:
    _cancelled.add(scan_id)


def is_running() -> bool:
    return _running_scan_id is not None


def current_scan_id() -> Optional[str]:
    return _running_scan_id


def _is_video(f: dict) -> bool:
    return (f.get("mime_type") or "").startswith("video/")


# --------------------------------------------------------------------------- #
# Scan
# --------------------------------------------------------------------------- #
async def run_scan(scan_id: str, resume_page_token: Optional[str] = None) -> None:
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

                await _process_new_files(scan_id, files, classifier)

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


async def _process_new_files(scan_id: str, files: list[dict], classifier) -> None:
    if not files:
        return

    async with get_db() as db:
        known = await models.existing_ids(db, [f["id"] for f in files])
        new_files = [f for f in files if f["id"] not in known]
        for f in new_files:
            await models.insert_photo_metadata(db, f, scan_batch=scan_id)
        await models.update_scan_progress(db, scan_id, total_files=len(new_files))
        await db.commit()

    if new_files:
        await _classify_batch(scan_id, new_files, classifier)


async def _classify_batch(scan_id: str, items: list[dict], classifier) -> None:
    """Classify a batch of items (images + videos) with per-type concurrency."""
    images = [f for f in items if not _is_video(f)]
    videos = [f for f in items if _is_video(f)]

    classified = failed = 0

    if images:
        sem = asyncio.Semaphore(THUMBNAIL_CONCURRENCY)

        async def do_image(f: dict):
            async with sem:
                return await _classify_image_item(f, classifier)

        for ok in await asyncio.gather(*(do_image(f) for f in images)):
            classified += 1 if ok else 0
            failed += 0 if ok else 1

    if videos and INCLUDE_VIDEOS:
        sem = asyncio.Semaphore(VIDEO_CONCURRENCY)

        async def do_video(f: dict):
            async with sem:
                return await _classify_video_item(f, classifier)

        for ok in await asyncio.gather(*(do_video(f) for f in videos)):
            classified += 1 if ok else 0
            failed += 0 if ok else 1

    async with get_db() as db:
        await models.update_scan_progress(
            db, scan_id, classified=classified, failed=failed
        )
        await db.commit()


# --------------------------------------------------------------------------- #
# Per-item classification (shared by scan and retry)
# --------------------------------------------------------------------------- #
async def _classify_image_item(f: dict, classifier) -> bool:
    try:
        thumb = await drive_service.download_thumbnail(
            f["id"], f["thumbnail_url"], str(THUMBNAIL_DIR)
        )
    except Exception as exc:
        await _record_failure(f["id"], f"thumbnail: {exc}")
        return False

    async with get_db() as db:
        await models.set_thumbnail_path(db, f["id"], thumb)
        await db.commit()

    try:
        result = await classifier.classify_image(thumb)
    except Exception as exc:
        await _record_failure(f["id"], f"classify: {exc}")
        return False

    async with get_db() as db:
        await models.save_classification(db, f["id"], result)
        await db.commit()
    return True


async def _classify_video_item(f: dict, classifier) -> bool:
    file_id = f["id"]
    size = f.get("size_bytes") or 0

    # Oversized videos: skip the full download, classify the Drive thumbnail.
    if size and size > MAX_VIDEO_BYTES:
        if f.get("thumbnail_url"):
            return await _classify_image_item(f, classifier)
        await _record_failure(file_id, "video too large and no thumbnail")
        return False

    workdir = tempfile.mkdtemp(prefix=f"vid_{file_id}_")
    try:
        video_path = str(Path(workdir) / "video.bin")
        try:
            await drive_service.download_file_media(file_id, video_path)
        except Exception as exc:
            await _record_failure(file_id, f"video download: {exc}")
            return False

        try:
            frame_paths = await asyncio.to_thread(
                video_service.extract_frames, video_path, workdir, VIDEO_FRAMES
            )
        except Exception as exc:
            await _record_failure(file_id, f"frame extraction: {exc}")
            return False

        # Classify each frame.
        frame_results: list[dict] = []
        for fp in frame_paths:
            try:
                frame_results.append(await classifier.classify_image(fp))
            except Exception as exc:
                logger.warning("Frame classify failed for %s: %s", file_id, exc)

        if not frame_results:
            await _record_failure(file_id, "all frames failed to classify")
            return False

        result = video_service.aggregate(frame_results)

        # Save a representative frame as the video's thumbnail.
        rep = video_service.best_frame_path(frame_paths, frame_results)
        if rep:
            dest = Path(THUMBNAIL_DIR) / f"{file_id}.jpg"
            Path(THUMBNAIL_DIR).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(rep, dest)
            async with get_db() as db:
                await models.set_thumbnail_path(db, file_id, str(dest))
                await db.commit()

        async with get_db() as db:
            await models.save_classification(db, file_id, result)
            await db.commit()
        return True
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def _classify_item(f: dict, classifier) -> bool:
    return (
        await _classify_video_item(f, classifier)
        if _is_video(f) and INCLUDE_VIDEOS
        else await _classify_image_item(f, classifier)
    )


# --------------------------------------------------------------------------- #
# Retry failed
# --------------------------------------------------------------------------- #
async def run_retry(retry_id: str) -> None:
    """Re-classify every photo/video currently marked failed."""
    global _running_scan_id

    if _running_lock.locked():
        logger.warning("A scan is already running; ignoring retry %s", retry_id)
        return

    async with _running_lock:
        _running_scan_id = retry_id
        _cancelled.discard(retry_id)
        classifier = get_classifier()
        try:
            async with get_db() as db:
                await models.create_scan_run(db, retry_id)
                failed = await models.failed_items(db)
                await models.update_scan_progress(
                    db, retry_id, total_files=len(failed)
                )
                # Reset them to pending so a crash mid-retry is visible.
                await models.reset_failed_to_pending(db, [r["id"] for r in failed])
                await db.commit()

            # Process in bounded batches so one huge failure set doesn't spike.
            batch: list[dict] = []
            for row in failed:
                batch.append(row)
                if len(batch) >= 50:
                    await _classify_batch(retry_id, batch, classifier)
                    batch = []
                if retry_id in _cancelled:
                    break
            if batch and retry_id not in _cancelled:
                await _classify_batch(retry_id, batch, classifier)

            await _finish(retry_id, "cancelled" if retry_id in _cancelled else "completed")
        except Exception:
            logger.exception("Retry %s failed", retry_id)
            await _finish(retry_id, "failed")
        finally:
            _running_scan_id = None
            await _aclose(classifier)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
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
