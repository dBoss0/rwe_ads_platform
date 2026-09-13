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
    logger.warning("frontend/dist not found — React build missing.")

    from fastapi.responses import HTMLResponse

    @app.get("/{full_path:path}", include_in_schema=False)
    async def no_frontend(full_path: str):
        return HTMLResponse("""
<!DOCTYPE html><html><head><title>RWE ADS Platform</title>
<style>body{font-family:sans-serif;background:#1a1410;color:#f0ebe6;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
.box{text-align:center;}.tag{background:#eb1700;color:#fff;font-size:.7rem;
font-weight:700;letter-spacing:.15em;padding:4px 12px;border-radius:4px;
text-transform:uppercase;}.h{font-size:1.8rem;font-weight:900;margin:1rem 0 .5rem;}
.sub{color:#81766f;font-size:.85rem;}.code{font-family:monospace;background:#2a2420;
padding:.8rem 1.2rem;border-radius:8px;border-left:3px solid #eb1700;
margin:1.2rem auto;max-width:500px;text-align:left;font-size:.8rem;color:#69d0ff;}
</style></head><body><div class="box">
<div class="tag">RWE ADS Platform</div>
<div class="h">Frontend build missing</div>
<div class="sub">The app is running. The React UI just needs to be built once.</div>
<div class="code">In Databricks:<br>
1. Open <b>notebooks/build_frontend</b><br>
2. Attach to any cluster → <b>Run All</b><br>
3. Redeploy this app when it finishes</div>
<div class="sub">API is live at <a href="/api/docs" style="color:#eb1700">/api/docs</a></div>
</div></body></html>""", status_code=200)
