"""
FastAPI application — RWE ADS Automation Platform.

Architecture:
  /api/*       → backend routers (JSON)
  /*           → React app static files (from frontend/dist/)

Databricks Apps runs this via:
  uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.routers import health, protocol, attrition, notebook, catalog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RWE ADS Platform starting up.")
    yield
    logger.info("RWE ADS Platform shutting down.")


app = FastAPI(
    title="RWE ADS Automation Platform",
    description=(
        "Protocol → Attrition → ADS automation for Premier Healthcare Database. "
        "Powered by Databricks, Claude, and the AI Dev Kit."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS (allow React dev server in local dev) ────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ───────────────────────────────────────────────────────────────
app.include_router(health.router,    prefix="/api")
app.include_router(protocol.router,  prefix="/api/protocol")
app.include_router(attrition.router, prefix="/api/attrition")
app.include_router(notebook.router,  prefix="/api/notebook")
app.include_router(catalog.router,   prefix="/api/catalog")

# ── Serve React frontend (production build) ───────────────────────────────────
if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve React SPA — all non-API routes return index.html."""
        index = FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
else:
    logger.warning(
        "frontend/dist not found — React build missing. "
        "Run: cd frontend && npm install && npm run build"
    )
