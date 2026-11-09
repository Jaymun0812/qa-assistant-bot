"""Single demo server exposing SME Finder and PLM Issue Lookup, plus a chat-style web UI.

    python -m uvicorn mqlbot_demo.app:app --reload
    → http://localhost:8000      (bot simulator)
    → http://localhost:8000/docs (API docs)
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import __version__
from .plm_api import router as plm_router
from .sme_api import router as sme_router

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="MQL_PLMate Demo API",
    description="Offline demo of the SME Finder and PLM Issue Lookup services, backed by mock data.",
    version=__version__,
)
app.include_router(sme_router)
app.include_router(plm_router)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["Info"])
async def health():
    return {"status": "ok", "mode": "demo"}
