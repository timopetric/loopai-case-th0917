"""Session verification — used by the frontend sign-in screen.

Auth itself is enforced once, at the /api/v1 router level (deps.py); this
route carries no auth logic of its own. Reaching the handler at all is proof
the submitted key was accepted, which is exactly what the sign-in screen
needs to know before it stops showing the sign-in form.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/session")
def verify_session() -> dict[str, bool]:
    return {"authenticated": True}
