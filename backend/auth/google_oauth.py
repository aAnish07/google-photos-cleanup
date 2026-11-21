"""Google OAuth2 flow and credential persistence for Drive access.

Uses an installed/desktop OAuth client (`backend/auth/credentials.json`). After
the user completes consent, the refresh token is stored in
`backend/auth/token.json` and reused on subsequent runs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from config import CREDENTIALS_PATH, GOOGLE_SCOPES, OAUTH_REDIRECT_URI, TOKEN_PATH


class CredentialsMissing(RuntimeError):
    """Raised when no valid Google credentials are available."""


def _require_client_config() -> None:
    if not Path(CREDENTIALS_PATH).exists():
        raise CredentialsMissing(
            f"Google OAuth client config not found at {CREDENTIALS_PATH}. "
            "Create a Desktop OAuth client in Google Cloud, enable the Drive API, "
            "and download it to backend/auth/credentials.json."
        )


def build_flow(state: Optional[str] = None) -> Flow:
    _require_client_config()
    return Flow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        scopes=GOOGLE_SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI,
        state=state,
    )


def get_authorization_url() -> tuple[str, str]:
    """Return (authorization_url, state) to redirect the user to consent."""
    flow = build_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # force a refresh token on re-auth
    )
    return url, state


def fetch_and_store_token(authorization_response_url: str, state: str) -> None:
    """Exchange the callback URL for tokens and persist them."""
    flow = build_flow(state=state)
    flow.fetch_token(authorization_response=authorization_response_url)
    _save_credentials(flow.credentials)


def _save_credentials(creds: Credentials) -> None:
    Path(TOKEN_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def load_credentials() -> Credentials:
    """Load stored credentials, refreshing them if expired. Raises if absent."""
    if not Path(TOKEN_PATH).exists():
        raise CredentialsMissing(
            "Not authenticated with Google yet. Visit /auth/login to connect Drive."
        )
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    creds = Credentials.from_authorized_user_info(data, scopes=GOOGLE_SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_credentials(creds)
        else:
            raise CredentialsMissing(
                "Google credentials are invalid and cannot be refreshed. "
                "Re-authenticate at /auth/login."
            )
    return creds


def is_authenticated() -> bool:
    try:
        load_credentials()
        return True
    except Exception:
        return False
