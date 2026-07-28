from __future__ import annotations

from datetime import date

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
    as_of: date | None = None,
) -> PipelineResult:
    """Run the B→A→B analysis path without starting an HTTP server."""
    request = build_case_request(prompt, case_id=case_id, session_id=session_id, as_of=as_of)
    analysis = server_app.analyze_case(request)
    response_view = compose_case_response(analysis)
    return PipelineResult(request=request, analysis=analysis, response_view=response_view)
