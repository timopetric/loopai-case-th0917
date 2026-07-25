"""Auth dependency for the /api/v1 router — attached ONCE at router level
(app/api/v1/router.py), never per-route, so a route added in a later slice
cannot ship unprotected by accident (architecture.md §3, PLAYBOOK.md §4).
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

# auto_error=False so a missing header and a wrong one collapse into the same
# 401 shape below, rather than FastAPI's own auto-403 for a missing header.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: str | None = Depends(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Reject any request whose ``X-API-Key`` does not match the shared key.

    Compared with ``secrets.compare_digest`` so a wrong or missing key can't
    be distinguished by timing. Never logs the key and never includes it (or
    the submitted value) in the error body — the exception detail is a fixed
    generic string.
    """
    if api_key is None or not secrets.compare_digest(api_key, settings.app_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
