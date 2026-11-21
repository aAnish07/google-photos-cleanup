"""Classifier abstraction.

The scanner depends only on the `Classifier` protocol, so the real Jev
implementation (`jev_service.JevClassifier`) and the offline `StubClassifier`
are interchangeable. Select via config.CLASSIFIER_BACKEND.

Every implementation returns the same result shape:

    {
        "photo_type":     {"choice": "screenshot",    "confidence": 0.92},
        "keep_signal":    {"choice": "likely_delete",  "confidence": 0.85},
        "has_text":       {"choice": "yes",            "confidence": 0.97},
        "quality_signal": {"choice": "medium",         "confidence": 0.74},
    }
"""
from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

# The classification questions, expressed in the TypeSafe "Choice" primitive
# shape: each question has `instructions` and a `criteria` map of
# {option_name: description}. This is the single source of truth for both the
# Jev request payload (JevClassifier builds Choice questions from it) and the
# stub's possible answers (it picks from the criteria keys).
#
# We model all four as Choice questions so every answer comes back as
# {choice, confidence}, matching the DB columns. The image is referenced from
# `state` via a placeholder; see jev_service.py.
IMAGE_REF = "photo"  # placeholder key in state that the image replaces

QUESTIONS: dict[str, dict] = {
    "photo_type": {
        "instructions": f"What type of photo is `{IMAGE_REF}`?",
        "criteria": {
            "screenshot": "A screenshot of a phone or computer screen, app, or webpage.",
            "scenery_landscape": "Outdoor scenery, nature, or landscape with no primary subject.",
            "people_portrait": "One or more people as the clear subject.",
            "selfie": "A self-portrait taken at arm's length or in a mirror.",
            "food_drink": "A meal, dish, drink, or food item.",
            "document_text": "A document, note, whiteboard, or page of text.",
            "meme_funny": "A meme, joke image, or funny captioned picture.",
            "receipt_bill": "A receipt, bill, invoice, or ticket.",
            "pet_animal": "A pet or animal as the subject.",
            "artwork_design": "Artwork, illustration, design, or graphic.",
            "event_celebration": "A party, wedding, concert, or other celebration.",
            "travel_landmark": "A landmark, monument, or recognizable travel destination.",
            "product_shopping": "A product, item for sale, or shopping photo.",
            "vehicle": "A car, bike, plane, boat, or other vehicle.",
            "interior_exterior": "The inside or outside of a building or room.",
            "other": "None of the other categories clearly fit.",
        },
    },
    "keep_signal": {
        "instructions": (
            f"How likely is the owner to want to keep `{IMAGE_REF}` in their "
            "personal photo library?"
        ),
        "criteria": {
            "definitely_keep": "Clearly valuable: sharp photos of people, travel, events, or memories.",
            "maybe_keep": "Possibly worth keeping, but not clearly valuable.",
            "likely_delete": "Probably clutter: random, redundant, or low value.",
            "definitely_delete": (
                "Clearly deletable: blurry, duplicate-looking, accidental, a random "
                "screenshot, or a receipt."
            ),
        },
    },
    "has_text": {
        "instructions": f"Does `{IMAGE_REF}` contain significant text?",
        "criteria": {
            "yes": "Contains significant text, like a screenshot, document, or message.",
            "no": "Contains little or no meaningful text.",
        },
    },
    "quality_signal": {
        "instructions": f"What is the visual quality of `{IMAGE_REF}`?",
        "criteria": {
            "high": "Sharp, well exposed, and visually clear.",
            "medium": "Acceptable but not great.",
            "low": "Poor quality: noisy, badly exposed, or cluttered.",
            "blurry": "Noticeably blurry or out of focus.",
        },
    },
}


@runtime_checkable
class Classifier(Protocol):
    async def classify_image(self, image_path: str) -> dict[str, dict]:
        """Classify a single image file. Returns the result shape above.

        Raises on failure; the scanner catches and records the error.
        """
        ...


class StubClassifier:
    """Deterministic offline classifier for development and tests.

    Produces stable pseudo-labels derived from the image file's bytes so the
    full pipeline (scan -> store -> filter -> UI) can be exercised without the
    real Jev API. NOT a real classifier — do not ship cleanup decisions made
    from these labels.
    """

    async def classify_image(self, image_path: str) -> dict[str, dict]:
        with open(image_path, "rb") as f:
            digest = hashlib.sha256(f.read()).digest()

        def pick(key: str, byte_index: int) -> dict:
            options = list(QUESTIONS[key]["criteria"].keys())
            choice = options[digest[byte_index] % len(options)]
            # Map a second byte to a confidence in [0.60, 0.99]
            confidence = round(0.60 + (digest[byte_index + 1] / 255) * 0.39, 2)
            return {"choice": choice, "confidence": confidence}

        return {
            "photo_type": pick("photo_type", 0),
            "keep_signal": pick("keep_signal", 2),
            "has_text": pick("has_text", 4),
            "quality_signal": pick("quality_signal", 6),
        }


def get_classifier() -> Classifier:
    """Factory selecting the classifier backend from config."""
    from config import CLASSIFIER_BACKEND

    if CLASSIFIER_BACKEND == "jev":
        from services.jev_service import JevClassifier

        return JevClassifier()
    return StubClassifier()
