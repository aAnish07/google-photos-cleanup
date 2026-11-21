"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    routes_auth,
    routes_photos,
    routes_scan,
    routes_stats,
    routes_trash,
)
from config import CLASSIFIER_BACKEND, FRONTEND_ORIGIN
from db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Google Photos Clean-Up", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_scan.router)
app.include_router(routes_photos.router)
app.include_router(routes_trash.router)
app.include_router(routes_stats.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "classifier_backend": CLASSIFIER_BACKEND}
