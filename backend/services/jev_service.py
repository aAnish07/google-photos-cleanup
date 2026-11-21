"""Jev (TypeSafe System One) classifier client.

Implements the `Classifier` protocol against the real TypeSafe API, verified
against the OpenAPI spec at https://docs.typesafe.ai/api/system-one and the
image guide at https://docs.typesafe.ai/images.

Contract summary (System One, POST /v1/systemone):
  - Auth: `Authorization: Bearer <TYPESAFE_API_KEY>`
  - Image requests MUST send header `TypeSafe-Danger-Zone-Images: true`
  - Request body:
        {
          "model": "jev-latest",
          "state": {"photo": "<ref>"},
          "assets": {"<ref>": {"type": "image", "part": "image"}},   # multipart
          "questions": {
            "<name>": {"type": "choice", "instructions": "...",
                       "criteria": {"opt": "description", ...}}
          }
        }
    The image is sent as a multipart file part; its asset `part` names that part.
  - Response:
        {"model": "...",
         "answers": {"<name>": {"type": "choice", "choice": "opt",
                                "confidence": 0.7,
                                "probabilities": {"opt": 0.8, ...}}},
         "usage": {"input_tokens": N, "output_tokens": M}}

Images must be PNG/JPEG, each side 280-1568px, total area 78,400-2,458,624px,
<=16 MiB/image, request body <=32 MiB. We prepare each image with Pillow first.
"""
from __future__ import annotations

import asyncio
import io
import json
import uuid

import httpx
from PIL import Image, ImageOps

from config import (
    CLASSIFY_CONCURRENCY,
    JEV_ENDPOINT,
    JEV_MODEL,
    JEV_TIMEOUT,
    THUMBNAIL_MAX_DIM,
    THUMBNAIL_MIN_DIM,
    TYPESAFE_API_KEY,
)
from services.classifier import IMAGE_REF, QUESTIONS

_MULTIPART_IMAGE_PART = "image"


class JevError(RuntimeError):
    """Raised when the Jev API returns an error or an unexpected payload."""


def prepare_jpeg(image_path: str) -> bytes:
    """Load an image and return baseline-JPEG bytes within Jev's size limits.

    - Rotates pixels upright (EXIF is stripped by the API, so we bake it in).
    - Shrinks so the longest side is <= THUMBNAIL_MAX_DIM (1568).
    - Pads so the shortest side is >= THUMBNAIL_MIN_DIM (280), since Jev rejects
      images with any side under the minimum (it never upscales for you).
    """
    with Image.open(image_path) as original:
        img = ImageOps.exif_transpose(original)
        img = img.convert("RGB")

        # Shrink longest side to the max (thumbnail only ever shrinks).
        img.thumbnail((THUMBNAIL_MAX_DIM, THUMBNAIL_MAX_DIM))

        w, h = img.size
        if min(w, h) < THUMBNAIL_MIN_DIM:
            # Pad (don't stretch) the short side up to the minimum, centered.
            target = (max(w, THUMBNAIL_MIN_DIM), max(h, THUMBNAIL_MIN_DIM))
            img = ImageOps.pad(img, target, color=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)  # baseline JPEG
        return buf.getvalue()


def build_request_body() -> dict:
    """Build the JSON body (minus the asset bytes) for one image classification."""
    questions = {
        name: {
            "type": "choice",
            "instructions": q["instructions"],
            "criteria": q["criteria"],
        }
        for name, q in QUESTIONS.items()
    }
    # Use a fresh reference so it can't collide with any text in the request.
    ref = f"{IMAGE_REF}-{uuid.uuid4()}"
    # Re-point every question's instructions placeholder to the unique ref.
    for q in questions.values():
        q["instructions"] = q["instructions"].replace(f"`{IMAGE_REF}`", f"`{ref}`")
    return {
        "model": JEV_MODEL,
        "state": {IMAGE_REF: ref},
        "assets": {ref: {"type": "image", "part": _MULTIPART_IMAGE_PART}},
        "questions": questions,
    }


class JevClassifier:
    """Async client for the TypeSafe System One classification endpoint."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or TYPESAFE_API_KEY
        if not self.api_key:
            raise JevError(
                "TYPESAFE_API_KEY is not set. Put it in backend/.env, or set "
                "CLASSIFIER_BACKEND=stub to run without the real API."
            )
        self._sem = asyncio.Semaphore(CLASSIFY_CONCURRENCY)
        self._client = httpx.AsyncClient(timeout=JEV_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "JevClassifier":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "TypeSafe-Danger-Zone-Images": "true",
        }

    async def classify_image(self, image_path: str) -> dict[str, dict]:
        img_bytes = await asyncio.to_thread(prepare_jpeg, image_path)
        body = build_request_body()

        # Multipart: JSON part named `request` first, then the image file part.
        files = [
            ("request", (None, json.dumps(body), "application/json")),
            (_MULTIPART_IMAGE_PART, ("image.jpg", img_bytes, "image/jpeg")),
        ]

        async with self._sem:
            resp = await self._client.post(
                JEV_ENDPOINT, headers=self._headers, files=files
            )

        if resp.status_code != 200:
            raise JevError(f"Jev returned {resp.status_code}: {_error_detail(resp)}")

        try:
            answers = resp.json()["answers"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise JevError(f"Unexpected Jev response: {resp.text[:300]}") from exc

        return self._parse_answers(answers)

    @staticmethod
    def _parse_answers(answers: dict) -> dict[str, dict]:
        """Map Jev Choice answers to our uniform {choice, confidence} shape."""
        result: dict[str, dict] = {}
        for name in QUESTIONS:
            ans = answers.get(name)
            if not ans or "choice" not in ans:
                raise JevError(f"Jev response missing answer for '{name}': {ans!r}")
            result[name] = {
                "choice": ans["choice"],
                "confidence": ans.get("confidence"),
            }
        return result


def _error_detail(resp: httpx.Response) -> str:
    try:
        return json.dumps(resp.json().get("detail", resp.text))[:300]
    except json.JSONDecodeError:
        return resp.text[:300]
