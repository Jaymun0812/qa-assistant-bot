"""PLM Issue Lookup API (demo): mock PLM data, same response contract as production."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from . import plm_lookup, summarizer
from .plm_client import MockPLMClient

router = APIRouter(prefix="/api/aibuilder", tags=["PLM Issue Lookup"])


def _client(request: Request) -> MockPLMClient:
    if not hasattr(request.app.state, "plm_client"):
        request.app.state.plm_client = MockPLMClient()
    return request.app.state.plm_client


@router.api_route("/issue-lookup", methods=["GET", "POST"])
async def issue_lookup(request: Request):
    if request.method == "GET":
        body = dict(request.query_params)
    else:
        try:
            body = json.loads(await request.body() or b"{}")
        except json.JSONDecodeError:
            body = {}
    issue_number = plm_lookup.extract_issue_number(body if isinstance(body, dict) else {})
    return await plm_lookup.lookup_issue(_client(request), issue_number)


class SummaryRequest(BaseModel):
    text: str
    issue_number: Optional[str] = None
    cause: Optional[str] = None
    countermeasure: Optional[str] = None


@router.post("/ai-summary")
async def ai_summary(body: SummaryRequest):
    return await summarizer.summarize(body.text, body.cause, body.countermeasure)
