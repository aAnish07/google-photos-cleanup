"""Google OAuth routes: start consent and handle the callback."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from auth import google_oauth
from config import FRONTEND_ORIGIN

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory store of the OAuth `state` and PKCE `code_verifier` between login
# and callback. Single-user local app, so a module global is sufficient.
_pending: dict[str, str] = {}


@router.get("/status")
async def auth_status() -> dict:
    return {"authenticated": google_oauth.is_authenticated()}


@router.get("/login")
async def login() -> RedirectResponse:
    url, state, code_verifier = google_oauth.get_authorization_url()
    _pending["state"] = state
    _pending["code_verifier"] = code_verifier
    return RedirectResponse(url)


@router.get("/callback")
async def callback(request: Request) -> HTMLResponse:
    state = _pending.get("state", "")
    code_verifier = _pending.get("code_verifier")
    try:
        google_oauth.fetch_and_store_token(str(request.url), state, code_verifier)
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(
            f"<h2>Authentication failed</h2><pre>{exc}</pre>", status_code=400
        )
    # Bounce back to the frontend.
    return HTMLResponse(
        f"""
        <html><body>
          <h2>Google Drive connected ✅</h2>
          <p>You can close this tab and return to the app.</p>
          <script>setTimeout(function(){{window.location='{FRONTEND_ORIGIN}';}}, 1200);</script>
        </body></html>
        """
    )
