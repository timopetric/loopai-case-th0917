"""The /api/v1 aggregate router.

The auth dependency is attached ONCE here, at the aggregate-router level
(architecture.md §3, PLAYBOOK.md §4) — never per-route — so any router
included below, including ones added in later slices, is protected without
anyone needing to remember to add auth to it individually. `/healthz` stays
outside this router entirely (mounted directly on the app in main.py) so it
remains public.
"""

from fastapi import APIRouter, Depends

from app.api.v1.deps import require_api_key
from app.api.v1.routers.agent import router as agent_router
from app.api.v1.routers.assumptions import router as assumptions_router
from app.api.v1.routers.export import router as export_router
from app.api.v1.routers.meta import router as meta_router
from app.api.v1.routers.report import router as report_router
from app.api.v1.routers.session import router as session_router
from app.api.v1.routers.spec import router as spec_router

api_router = APIRouter(dependencies=[Depends(require_api_key)])

api_router.include_router(session_router)
api_router.include_router(meta_router)
api_router.include_router(report_router)
api_router.include_router(export_router)
api_router.include_router(assumptions_router)
api_router.include_router(spec_router)
api_router.include_router(agent_router)
