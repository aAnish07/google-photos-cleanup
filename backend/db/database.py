"""SQLite connection management and schema initialization."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

from config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,                    -- Google Drive file ID
    name TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    created_time TEXT,                      -- ISO 8601 from Drive
    modified_time TEXT,
    thumbnail_path TEXT,                    -- Local path to cached thumbnail
    thumbnail_url TEXT,                     -- Drive thumbnail URL
    web_view_link TEXT,                     -- Link to view in Drive

    -- Classification results
    photo_type TEXT,
    photo_type_confidence REAL,
    keep_signal TEXT,
    keep_signal_confidence REAL,
    has_text TEXT,
    has_text_confidence REAL,
    quality_signal TEXT,
    quality_signal_confidence REAL,

    -- State
    classification_status TEXT DEFAULT 'pending',  -- pending, classified, failed
    classification_error TEXT,
    classified_at TEXT,
    trashed INTEGER DEFAULT 0,             -- 1 if user approved for trash
    trashed_at TEXT,
    scan_batch TEXT,                        -- Which scan run found this

    created_in_db TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_photo_type ON photos(photo_type);
CREATE INDEX IF NOT EXISTS idx_keep_signal ON photos(keep_signal);
CREATE INDEX IF NOT EXISTS idx_created_time ON photos(created_time);
CREATE INDEX IF NOT EXISTS idx_trashed ON photos(trashed);
CREATE INDEX IF NOT EXISTS idx_classification_status ON photos(classification_status);

CREATE TABLE IF NOT EXISTS scan_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',         -- running, completed, failed, cancelled
    total_files INTEGER DEFAULT 0,
    classified INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    next_page_token TEXT
);

-- Records each batch of trash/untrash actions so the user can undo.
CREATE TABLE IF NOT EXISTS trash_batches (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,                  -- trash | untrash
    created_at TEXT DEFAULT (datetime('now')),
    file_ids TEXT NOT NULL                 -- JSON array of Drive file IDs that succeeded
);
"""


async def init_db() -> None:
    """Create the data dir and initialize the schema."""
    ensure_dirs()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield a connection with row access by column name and FK enforcement."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()
