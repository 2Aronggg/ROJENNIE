from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from server.agent.response_composer import CaseResponseView, compose_case_response
from server.agent.router import build_case_request
from server import app as server_app
from server.schemas import CaseAnalysis, CaseAnalyzeRequest


class PipelineResult(BaseModel):
    request: CaseAnalyzeRequest
    analysis: CaseAnalysis
    response_view: CaseResponseView


def run_analysis(
    prompt: str,
    *,
    case_id: str | None = None,
    session_id: str | None = None,
    customer_id: str | None = "CUST-001",
    as_of: date | None = None,
    use_llm: bool | None = None,
    router_client: Any | None = None,
) -> PipelineResult:
    """Run the B→A→B analysis path without starting an HTTP server."""
    request = build_case_request(prompt, case_id=case_id, session_id=session_id, customer_id=customer_id, as_of=as_of, use_llm=use_llm, client=router_client)
    analysis = server_app.analyze_case(request)
    response_view = compose_case_response(analysis)
    return PipelineResult(request=request, analysis=analysis, response_view=response_view)
