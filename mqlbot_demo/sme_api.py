"""SME Finder API (demo): same request/response contract as the production service."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from . import sme_search

DATA_FILE = Path(__file__).parent / "data" / "sme_data.json"
QUERY_LOG_LIMIT = 200

router = APIRouter(prefix="/api", tags=["SME Finder"])

Expander = Callable[[str], Awaitable[list[str]]]


class FindSMERequest(BaseModel):
    query: str
    top_k: Optional[Union[str, int]] = "all"
    team_filter: Optional[str] = None

    @field_validator("top_k", mode="before")
    @classmethod
    def validate_top_k(cls, v):
        sme_search.parse_top_k(v)  # raises ValueError for invalid values
        return v


def load_sme_data(path: Path = DATA_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


async def no_expansion(query: str) -> list[str]:
    return []


def _state(request: Request):
    state = request.app.state
    if not hasattr(state, "sme_data"):
        state.sme_data = load_sme_data()
        state.query_log = []
        state.sme_expander = no_expansion
    return state


@router.post("/find-sme")
async def find_sme(body: FindSMERequest, request: Request):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")
    state = _state(request)

    candidates = sme_search.search(query, state.sme_data, body.top_k, body.team_filter)
    expanded: list[str] = []
    if not candidates:
        # optional LLM step: expand synonyms only when keyword search finds nothing
        expanded = await state.sme_expander(query)
        if expanded:
            candidates = sme_search.search(query, state.sme_data, body.top_k, body.team_filter, expanded)

    state.query_log.append({
        "query": query, "result_count": len(candidates),
        "top_result": candidates[0]["name"] if candidates else "", "time": datetime.now().isoformat(timespec="seconds"),
    })
    del state.query_log[:-QUERY_LOG_LIMIT]

    return {
        "query": query,
        "total_count": len(candidates),
        "candidates": candidates,
        "expanded_keywords": expanded,
        "formatted_result": sme_search.format_result(query, candidates),
        **sme_search.flatten_candidates(candidates),
    }


@router.get("/teams")
async def teams(request: Request):
    return {"teams": sorted({s["team"] for s in _state(request).sme_data})}


@router.get("/sme-list")
async def sme_list(request: Request):
    grouped: dict[str, list[dict]] = {}
    for s in _state(request).sme_data:
        grouped.setdefault(s["team"], []).append({"name": s["name"], "knox_id": s["knox_id"], "sme": s["sme"]})
    return {"teams": grouped}


@router.get("/query-log")
async def query_log(request: Request, limit: int = 20):
    return {"logs": list(reversed(_state(request).query_log))[:limit]}
