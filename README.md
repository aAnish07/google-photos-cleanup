# Google Photos Clean-Up Tool

Scan the images in your Google Drive, classify each one with **Jev** (TypeSafe's
System One model), then review, filter, and bulk-trash unwanted photos from a web
UI. Deletions are **trash-only** — files go to Google Drive's trash (30-day
recovery), never permanent delete.

> Status: backend complete and verified against the live Jev API; React
> frontend built and type-checked. Ready to run once you add Google Drive
> OAuth credentials and a TypeSafe API key.

## Architecture

```
Google Drive API (list + download thumbnails)
    -> Prepare image (Pillow: EXIF-upright, 280-1568px per Jev limits)
    -> Jev /v1/systemone (classify each image with Choice questions)
    -> SQLite (labels, confidence, Drive metadata)
    -> FastAPI (serves API + deletion endpoints)
    -> React frontend (browse, filter, preview, approve deletions)
    -> Google Drive API (trash approved photos)
```

## Classifier contract (verified)

Jev is TypeSafe's "System One" API. Verified against
https://docs.typesafe.ai/api/system-one and https://docs.typesafe.ai/images:

- **Endpoint:** `POST https://api.typesafe.ai/v1/systemone`
- **Auth:** `Authorization: Bearer <TYPESAFE_API_KEY>`
- **Images:** require header `TypeSafe-Danger-Zone-Images: true`; sent as a
  multipart file part (recommended) referenced from `state` via an `assets` map.
- **Questions:** we ask four `choice` questions (photo_type, keep_signal,
  has_text, quality_signal); each answer returns `{choice, confidence,
  probabilities}`.
- **Model:** `jev-latest` (image support needs Jev 1.13/1.14).
- **Image limits:** PNG/JPEG, each side 280-1568px, <=16 MiB/image.

The single source of truth for the questions is `backend/services/classifier.py`.
A `StubClassifier` provides deterministic offline labels so the pipeline runs
without the API (`CLASSIFIER_BACKEND=stub`).

## Prerequisites

1. Python 3.11+, Node.js 18+
2. A Google Cloud project with the **Drive API enabled** and an OAuth **Desktop**
   client. Download it to `backend/auth/credentials.json`.
3. A TypeSafe API key — https://console.typesafe.ai (put it in `backend/.env`).

## Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # fill in TYPESAFE_API_KEY
uvicorn main:app --reload --port 8000
```

Then connect Drive: open `http://localhost:8000/auth/login` (or use the app's
Connect button) and complete Google consent. The refresh token is stored in
`backend/auth/token.json`.

### Key endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/health` | Health + active classifier backend |
| GET  | `/auth/status`, `/auth/login`, `/auth/callback` | Google OAuth |
| GET  | `/api/scan/library-size` | Exact image count + total size (no classify) |
| POST | `/api/scan/start`, `/api/scan/cancel` | Start/resume, cancel a scan |
| GET  | `/api/scan/status` | Scan progress |
| GET  | `/api/photos` | Filtered, paginated photo list |
| GET  | `/api/photos/{id}`, `/api/photos/{id}/image` | Detail + cached thumbnail |
| POST | `/api/trash`, `/api/trash/undo` | Trash / undo (by ids or last batch) |
| POST | `/api/trash/by-filter` | Two-step confirm trash-by-filter |
| GET  | `/api/stats` | Category / keep-signal / month breakdowns |

## Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173, proxies /api -> :8000
```

## Safety

- **Never permanently deletes.** Only `files.update(trashed=true)`.
- Bulk trash is a two-step confirm (count + total size shown first).
- Every trashed batch is recorded so it can be undone.
- Trash calls are rate-limited (~2/s) to stay within Drive quota.
- Scans are resumable (saved Drive page token) and skip already-seen files.

## Secrets

`.env`, `credentials.json`, `token.json`, and the local `data/` cache are
git-ignored and never committed.
