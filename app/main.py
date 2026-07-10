import sys
from pathlib import Path

# Makes `from app.routers import ...` work even when this file is run directly
# (`python app/main.py`), not just via `uvicorn app.main:app` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

from app.config import settings  # noqa: E402
from app.routers import (  # noqa: E402
    admin,
    assignments,
    audit_trail,
    auth,
    calendar,
    dashboard,
    filesystem,
    imports,
    lookups,
    process_types,
    reports,
    taxonomy,
    users,
)

APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = APP_DIR.parent / "frontend" / "dist"

app = FastAPI(title="Project Management Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(imports.router)
app.include_router(admin.router)
app.include_router(assignments.router)
app.include_router(lookups.router)
app.include_router(users.router)
app.include_router(taxonomy.router)
app.include_router(filesystem.router)
app.include_router(process_types.router)
app.include_router(audit_trail.router)
app.include_router(calendar.router)
app.include_router(reports.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serves the built React app (frontend/dist, from `npm run build`) so a single
# process handles both API and UI - no separate Vite dev server needed in
# production. Registered LAST so /api/* routes above always match first; this
# catch-all only sees requests that missed every route above it.
#
# StaticFiles(html=True) was tried first but only serves index.html for exact
# directory matches, not for arbitrary React Router paths (e.g. /dashboard) -
# a hard refresh there 404s. A catch-all route serving index.html unless the
# path is a real built asset is the standard FastAPI/SPA pattern instead.
if FRONTEND_DIST.exists():
    frontend_root = FRONTEND_DIST.resolve()

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        candidate = (FRONTEND_DIST / full_path).resolve()
        is_real_asset = full_path and candidate.is_file() and frontend_root in candidate.parents
        return FileResponse(candidate if is_real_asset else FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(APP_DIR)],  # don't watch frontend/node_modules - huge and irrelevant
    )
