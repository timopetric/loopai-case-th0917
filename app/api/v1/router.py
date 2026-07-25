"""The /api/v1 aggregate router.

Empty this slice (walking skeleton — issue 01). Later slices attach the auth
dependency here once (architecture.md §3) and include per-domain routers
(report, export, agent, meta).
"""

from fastapi import APIRouter

api_router = APIRouter()
