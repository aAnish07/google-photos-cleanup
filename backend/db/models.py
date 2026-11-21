"""Query helpers for the photos, scan_runs, and trash_batches tables.

All functions take an open aiosqlite connection so callers control the
transaction/commit boundary.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

# Columns a client may sort by (whitelist to avoid SQL injection via `sort`).
SORTABLE = {"created_time", "size_bytes", "photo_type_confidence", "modified_time"}

# Fields accepted as list-valued filters.
_LIST_FILTERS = {
    "photo_type": "photo_type",
    "keep_signal": "keep_signal",
    "quality_signal": "quality_signal",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Photos
# --------------------------------------------------------------------------- #
async def photo_exists(db: aiosqlite.Connection, file_id: str) -> bool:
    cur = await db.execute("SELECT 1 FROM photos WHERE id = ?", (file_id,))
    return await cur.fetchone() is not None


async def existing_ids(db: aiosqlite.Connection, file_ids: list[str]) -> set[str]:
    """Return the subset of file_ids already present in the photos table."""
    if not file_ids:
        return set()
    placeholders = ",".join("?" for _ in file_ids)
    cur = await db.execute(
        f"SELECT id FROM photos WHERE id IN ({placeholders})", file_ids
    )
    return {row["id"] for row in await cur.fetchall()}


async def insert_photo_metadata(
    db: aiosqlite.Connection, meta: dict[str, Any], scan_batch: str
) -> None:
    """Insert a Drive file's metadata (pre-classification). Idempotent."""
    await db.execute(
        """
        INSERT OR IGNORE INTO photos
            (id, name, mime_type, size_bytes, created_time, modified_time,
             thumbnail_url, web_view_link, scan_batch, classification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """,
        (
            meta["id"],
            meta.get("name"),
            meta.get("mime_type"),
            meta.get("size_bytes"),
            meta.get("created_time"),
            meta.get("modified_time"),
            meta.get("thumbnail_url"),
            meta.get("web_view_link"),
            scan_batch,
        ),
    )


async def set_thumbnail_path(
    db: aiosqlite.Connection, file_id: str, path: str
) -> None:
    await db.execute(
        "UPDATE photos SET thumbnail_path = ? WHERE id = ?", (path, file_id)
    )


async def save_classification(
    db: aiosqlite.Connection, file_id: str, result: dict[str, dict]
) -> None:
    """Persist a classification result.

    `result` shape: {question_key: {"choice": str, "confidence": float}, ...}
    """
    def choice(k: str) -> Optional[str]:
        return result.get(k, {}).get("choice")

    def conf(k: str) -> Optional[float]:
        return result.get(k, {}).get("confidence")

    await db.execute(
        """
        UPDATE photos SET
            photo_type = ?, photo_type_confidence = ?,
            keep_signal = ?, keep_signal_confidence = ?,
            has_text = ?, has_text_confidence = ?,
            quality_signal = ?, quality_signal_confidence = ?,
            classification_status = 'classified',
            classification_error = NULL,
            classified_at = ?
        WHERE id = ?
        """,
        (
            choice("photo_type"), conf("photo_type"),
            choice("keep_signal"), conf("keep_signal"),
            choice("has_text"), conf("has_text"),
            choice("quality_signal"), conf("quality_signal"),
            _now(), file_id,
        ),
    )


async def mark_classification_failed(
    db: aiosqlite.Connection, file_id: str, error: str
) -> None:
    await db.execute(
        """
        UPDATE photos
        SET classification_status = 'failed', classification_error = ?
        WHERE id = ?
        """,
        (error[:500], file_id),
    )


def _build_filters(params: dict[str, Any]) -> tuple[str, list[Any]]:
    """Build a WHERE clause (and args) from the photo filter params."""
    clauses: list[str] = []
    args: list[Any] = []

    # trashed: default to not-trashed
    trashed = params.get("trashed")
    if trashed in (True, "true", 1, "1"):
        clauses.append("trashed = 1")
    elif trashed in (False, "false", 0, "0", None):
        clauses.append("trashed = 0")

    for key, column in _LIST_FILTERS.items():
        values = params.get(key)
        if values:
            if isinstance(values, str):
                values = [v for v in values.split(",") if v]
            if values:
                placeholders = ",".join("?" for _ in values)
                clauses.append(f"{column} IN ({placeholders})")
                args.extend(values)

    if params.get("has_text") in ("yes", "no"):
        clauses.append("has_text = ?")
        args.append(params["has_text"])

    if params.get("classification_status"):
        clauses.append("classification_status = ?")
        args.append(params["classification_status"])

    if params.get("date_from"):
        clauses.append("created_time >= ?")
        args.append(params["date_from"])
    if params.get("date_to"):
        clauses.append("created_time <= ?")
        args.append(params["date_to"])

    if params.get("min_size") is not None:
        clauses.append("size_bytes >= ?")
        args.append(params["min_size"])
    if params.get("max_size") is not None:
        clauses.append("size_bytes <= ?")
        args.append(params["max_size"])

    if params.get("min_confidence") is not None:
        clauses.append("photo_type_confidence >= ?")
        args.append(params["min_confidence"])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, args


async def query_photos(
    db: aiosqlite.Connection, params: dict[str, Any]
) -> dict[str, Any]:
    """Return a paginated, filtered page of photos plus pagination metadata."""
    where, args = _build_filters(params)

    # total count
    cur = await db.execute(f"SELECT COUNT(*) AS c FROM photos{where}", args)
    total = (await cur.fetchone())["c"]

    sort = params.get("sort", "created_time")
    if sort not in SORTABLE:
        sort = "created_time"
    order = "ASC" if str(params.get("order", "desc")).lower() == "asc" else "DESC"

    page = max(1, int(params.get("page", 1)))
    per_page = min(200, max(1, int(params.get("per_page", 50))))
    offset = (page - 1) * per_page

    cur = await db.execute(
        f"SELECT * FROM photos{where} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        [*args, per_page, offset],
    )
    rows = [dict(r) for r in await cur.fetchall()]

    total_pages = (total + per_page - 1) // per_page
    return {
        "photos": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


async def ids_matching_filter(
    db: aiosqlite.Connection, params: dict[str, Any]
) -> list[str]:
    """Return every photo id matching a filter (used for trash-by-filter)."""
    where, args = _build_filters(params)
    cur = await db.execute(f"SELECT id FROM photos{where}", args)
    return [r["id"] for r in await cur.fetchall()]


async def get_photo(db: aiosqlite.Connection, file_id: str) -> Optional[dict]:
    cur = await db.execute("SELECT * FROM photos WHERE id = ?", (file_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def set_trashed(
    db: aiosqlite.Connection, file_ids: list[str], trashed: bool
) -> None:
    if not file_ids:
        return
    placeholders = ",".join("?" for _ in file_ids)
    ts = _now() if trashed else None
    await db.execute(
        f"UPDATE photos SET trashed = ?, trashed_at = ? WHERE id IN ({placeholders})",
        [1 if trashed else 0, ts, *file_ids],
    )


# --------------------------------------------------------------------------- #
# Scan runs
# --------------------------------------------------------------------------- #
async def create_scan_run(db: aiosqlite.Connection, scan_id: str) -> None:
    await db.execute(
        "INSERT INTO scan_runs (id, started_at, status) VALUES (?, ?, 'running')",
        (scan_id, _now()),
    )


async def update_scan_progress(
    db: aiosqlite.Connection,
    scan_id: str,
    *,
    total_files: Optional[int] = None,
    classified: Optional[int] = None,
    failed: Optional[int] = None,
    next_page_token: Optional[str] = None,
) -> None:
    sets, args = [], []
    if total_files is not None:
        sets.append("total_files = total_files + ?")
        args.append(total_files)
    if classified is not None:
        sets.append("classified = classified + ?")
        args.append(classified)
    if failed is not None:
        sets.append("failed = failed + ?")
        args.append(failed)
    if next_page_token is not None:
        sets.append("next_page_token = ?")
        args.append(next_page_token)
    if not sets:
        return
    args.append(scan_id)
    await db.execute(f"UPDATE scan_runs SET {', '.join(sets)} WHERE id = ?", args)


async def finish_scan_run(
    db: aiosqlite.Connection, scan_id: str, status: str
) -> None:
    await db.execute(
        "UPDATE scan_runs SET status = ?, completed_at = ?, next_page_token = NULL WHERE id = ?",
        (status, _now(), scan_id),
    )


async def set_scan_status(
    db: aiosqlite.Connection, scan_id: str, status: str
) -> None:
    await db.execute("UPDATE scan_runs SET status = ? WHERE id = ?", (status, scan_id))


async def get_scan_run(db: aiosqlite.Connection, scan_id: str) -> Optional[dict]:
    cur = await db.execute("SELECT * FROM scan_runs WHERE id = ?", (scan_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def latest_scan_run(db: aiosqlite.Connection) -> Optional[dict]:
    cur = await db.execute(
        "SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT 1"
    )
    row = await cur.fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- #
# Trash batches (for undo)
# --------------------------------------------------------------------------- #
async def record_trash_batch(
    db: aiosqlite.Connection, batch_id: str, action: str, file_ids: list[str]
) -> None:
    await db.execute(
        "INSERT INTO trash_batches (id, action, file_ids) VALUES (?, ?, ?)",
        (batch_id, action, json.dumps(file_ids)),
    )


async def latest_trash_batch(db: aiosqlite.Connection) -> Optional[dict]:
    cur = await db.execute(
        "SELECT * FROM trash_batches WHERE action = 'trash' ORDER BY created_at DESC LIMIT 1"
    )
    row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["file_ids"] = json.loads(d["file_ids"])
    return d


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #
async def _grouped(db: aiosqlite.Connection, column: str) -> dict[str, dict]:
    cur = await db.execute(
        f"""
        SELECT {column} AS k, COUNT(*) AS count, COALESCE(SUM(size_bytes), 0) AS size_bytes
        FROM photos
        WHERE trashed = 0 AND {column} IS NOT NULL
        GROUP BY {column}
        """
    )
    return {
        r["k"]: {"count": r["count"], "size_bytes": r["size_bytes"]}
        for r in await cur.fetchall()
    }


async def get_stats(db: aiosqlite.Connection) -> dict[str, Any]:
    cur = await db.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(size_bytes), 0) AS s FROM photos WHERE trashed = 0"
    )
    row = await cur.fetchone()

    # recoverable = size of likely_delete + definitely_delete
    cur = await db.execute(
        """
        SELECT COALESCE(SUM(size_bytes), 0) AS s
        FROM photos
        WHERE trashed = 0 AND keep_signal IN ('likely_delete', 'definitely_delete')
        """
    )
    recoverable = (await cur.fetchone())["s"]

    cur = await db.execute(
        """
        SELECT substr(created_time, 1, 7) AS ym, COUNT(*) AS count,
               COALESCE(SUM(size_bytes), 0) AS size_bytes
        FROM photos
        WHERE trashed = 0 AND created_time IS NOT NULL
        GROUP BY ym ORDER BY ym
        """
    )
    by_year_month = {
        r["ym"]: {"count": r["count"], "size_bytes": r["size_bytes"]}
        for r in await cur.fetchall()
    }

    return {
        "total_photos": row["c"],
        "total_size_bytes": row["s"],
        "estimated_recoverable_bytes": recoverable,
        "by_type": await _grouped(db, "photo_type"),
        "by_keep_signal": await _grouped(db, "keep_signal"),
        "by_quality": await _grouped(db, "quality_signal"),
        "by_year_month": by_year_month,
    }
