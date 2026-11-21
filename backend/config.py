"""Central configuration loaded from environment variables."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/ directory
BASE_DIR = Path(__file__).resolve().parent

# Load backend/.env if present
load_dotenv(BASE_DIR / ".env")

# --- Paths ---
AUTH_DIR = BASE_DIR / "auth"
DATA_DIR = BASE_DIR / "data"
THUMBNAIL_DIR = DATA_DIR / "thumbnails"
DB_PATH = DATA_DIR / "app.sqlite"

CREDENTIALS_PATH = AUTH_DIR / "credentials.json"
TOKEN_PATH = AUTH_DIR / "token.json"

# --- Google OAuth ---
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive"]
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# --- Jev / TypeSafe classifier ---
TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY")
JEV_ENDPOINT = os.getenv("JEV_ENDPOINT", "https://api.typesafe.ai/v1/systemone")
# `jev-latest` is the recommended alias; image support requires Jev 1.13/1.14,
# which jev-latest resolves to. Override via env if the account needs a pin.
JEV_MODEL = os.getenv("JEV_MODEL", "jev-latest")
# Request timeout (seconds) for a single classification call.
JEV_TIMEOUT = float(os.getenv("JEV_TIMEOUT", "60"))

# Which classifier implementation to use: "jev" (real API) or "stub" (offline, deterministic).
# Defaults to "stub" until the real Jev contract is wired and a key is present.
CLASSIFIER_BACKEND = os.getenv("CLASSIFIER_BACKEND", "jev" if TYPESAFE_API_KEY else "stub")

# --- Tunables ---
# Jev requires the image's min/max dimension within this range.
THUMBNAIL_MIN_DIM = 280
THUMBNAIL_MAX_DIM = 1568

# Rate limits (requests per second)
DRIVE_LIST_RPS = 5.0
DRIVE_TRASH_RPS = 2.0

# Concurrency
THUMBNAIL_CONCURRENCY = 10
CLASSIFY_CONCURRENCY = 8

# Drive listing page size
DRIVE_PAGE_SIZE = 100

# --- Video scanning ---
# Include videos in scans. Each video is sampled into VIDEO_FRAMES frames at
# evenly spaced positions (mid-interval), each frame is classified, and the
# per-frame answers are aggregated into one keep/delete judgment for the video.
INCLUDE_VIDEOS = os.getenv("INCLUDE_VIDEOS", "true").lower() in ("1", "true", "yes")
VIDEO_FRAMES = int(os.getenv("VIDEO_FRAMES", "10"))  # frames sampled per video
# Videos are downloaded in full to sample frames; cap the size we'll fetch.
# Over this, we fall back to classifying the Drive thumbnail (single frame).
MAX_VIDEO_BYTES = int(os.getenv("MAX_VIDEO_BYTES", str(500 * 1024 * 1024)))
VIDEO_CONCURRENCY = int(os.getenv("VIDEO_CONCURRENCY", "2"))

# CORS
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


def ensure_dirs() -> None:
    """Create local data directories if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
