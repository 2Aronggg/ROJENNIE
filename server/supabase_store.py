from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from .schemas import AuditEvent, CaseAnalysis, ReviewResponse


LOGGER = logging.getLogger(__name__)


class SupabaseStore:
    """Small REST adapter for deployed case persistence.

    The mock bank and RAG corpus stay local. This adapter only persists
    application-owned case, review, and audit records.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        customer_ref: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("SUPABASE_SECRET_KEY", "")
        self.customer_ref = customer_ref or os.getenv("SUPABASE_CUSTOMER_REF", "CUST-001")
        self._owner_id: str | None = None

    @property
    def enabled(self) -> bool:
        flag = os.getenv("SUPABASE_PERSISTENCE", os.getenv("SUPABASE_ENABLED", "false"))
        return flag.strip().lower() in {"1", "true", "yes", "on"} and bool(
            self.base_url and self.api_key
        )

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers = {"apikey": self.api_key, "Accept": "application/json"}
        # New sb_secret keys must not be sent as a JWT Bearer token.
        if not self.api_key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {self.api_key}"
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _request(
        self,
        table: str,
        *,
        method: str = "GET",
        params: dict[str, str] | None = None,
        body: Any | None = None,
        prefer: str | None = None,
    ) -> list[dict[str, Any]]:
        query = f"?{urlencode(params)}" if params else ""
        request = Request(
            f"{self.base_url}/rest/v1/{table}{query}",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
            headers=self._headers(json_body=body is not None)
            | ({"Prefer": prefer} if prefer else {}),
            method=method,
        )
        try:
            with urlopen(request, timeout=10) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            detail = ""
            if isinstance(exc, HTTPError):
                detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Supabase {method} {table} failed: {detail or exc}") from exc
        if not raw:
            return []
        result = json.loads(raw.decode("utf-8"))
        return result if isinstance(result, list) else [result]

    def _safe(self, operation: str, callback: Any, fallback: Any) -> Any:
        if not self.enabled:
            return fallback
        try:
            return callback()
        except Exception as exc:
            LOGGER.warning("Supabase persistence failed during %s: %s", operation, exc)
            return fallback

    def _owner(self) -> str | None:
        if self._owner_id:
            return self._owner_id
        configured = os.getenv("SUPABASE_OWNER_ID")
        if configured:
            self._owner_id = configured
            return configured
        rows = self._request(
            "profiles",
            params={
                "customer_ref": f"eq.{self.customer_ref}",
                "select": "id",
                "limit": "1",
            },
        )
        self._owner_id = str(rows[0]["id"]) if rows else None
        return self._owner_id

    def _case_uuid(self, case_id: str) -> str | None:
        rows = self._request(
            "cases",
            params={"case_id": f"eq.{case_id}", "select": "id", "limit": "1"},
        )
        return str(rows[0]["id"]) if rows else None

    def save_case(self, result: CaseAnalysis) -> bool:
        def operation() -> bool:
            owner_id = self._owner()
            if not owner_id:
                raise RuntimeError(f"profile not found for {self.customer_ref}")
            analysis = result.model_dump(mode="json")
            controls = [issue.decision.control for issue in result.issues]
            status = (
                "hold"
                if "hold" in controls
                else "amend"
                if "amend" in controls
                else "ask"
                if "ask" in controls
                else "proceed"
            )
            rows = self._request(
                "cases",
                method="POST",
                params={"on_conflict": "case_id"},
                body=[
                    {
                        "owner_id": owner_id,
                        "case_id": result.case_id,
                        "prompt": result.prompt,
                        "status": status,
                        "analysis": analysis,
                    }
                ],
                prefer="resolution=merge-duplicates,return=representation",
            )
            case_uuid = str(rows[0]["id"]) if rows and rows[0].get("id") else self._case_uuid(result.case_id)
            if not case_uuid:
                raise RuntimeError(f"case row was not returned for {result.case_id}")
            issue_rows = [
                {
                    "case_id": case_uuid,
                    "issue_id": issue.issue_id,
                    "product": issue.product,
                    "issue_type": issue.issue_type,
                    "decision": issue.decision.control,
                    "report": issue.report.model_dump(mode="json"),
                }
                for issue in result.issues
            ]
            if issue_rows:
                self._request(
                    "case_issues",
                    method="POST",
                    params={"on_conflict": "case_id,issue_id"},
                    body=issue_rows,
                    prefer="resolution=merge-duplicates,return=minimal",
                )
            return True

        return bool(self._safe("save_case", operation, False))

    def get_case(self, case_id: str) -> CaseAnalysis | None:
        def operation() -> CaseAnalysis | None:
            rows = self._request(
                "cases",
                params={"case_id": f"eq.{case_id}", "select": "analysis", "limit": "1"},
            )
            if not rows or not rows[0].get("analysis"):
                return None
            return CaseAnalysis.model_validate(rows[0]["analysis"])

        return self._safe("get_case", operation, None)

    def list_cases(self, limit: int = 30) -> list[dict[str, Any]]:
        """상담 이력 목록. 마이 페이지가 브라우저 저장소 대신 서버를 읽는다."""

        def operation() -> list[dict[str, Any]]:
            owner_id = self._owner()
            if not owner_id:
                return []
            return self._request(
                "cases",
                params={
                    "owner_id": f"eq.{owner_id}",
                    "select": "case_id,prompt,created_at,analysis",
                    "order": "created_at.desc",
                    "limit": str(limit),
                },
            )

        return self._safe("list_cases", operation, [])

    def save_review(self, response: ReviewResponse) -> bool:
        def operation() -> bool:
            case_uuid = self._case_uuid(response.case_id)
            if not case_uuid:
                return False
            issue_rows = self._request(
                "case_issues",
                params={"case_id": f"eq.{case_uuid}", "select": "id"},
            )
            if not issue_rows:
                return False
            reviewer_id = response.reviewer_id
            try:
                UUID(reviewer_id)
            except (ValueError, AttributeError):
                reviewer_id = None
            self._request(
                "reviews",
                method="POST",
                body=[
                    {
                        "case_issue_id": row["id"],
                        "reviewer_id": reviewer_id,
                        "status": "applied" if response.applied else "rejected",
                        "note": response.note,
                    }
                    for row in issue_rows
                ],
                prefer="return=minimal",
            )
            return True

        return bool(self._safe("save_review", operation, False))

    def save_audit(self, event: AuditEvent) -> bool:
        def operation() -> bool:
            case_uuid = self._case_uuid(event.case_id)
            if not case_uuid:
                return False
            payload = {
                **event.payload,
                "_event_id": event.event_id,
                "_actor": event.actor,
            }
            self._request(
                "audit_logs",
                method="POST",
                body=[
                    {
                        "case_id": case_uuid,
                        "event_type": event.event_type,
                        "payload": payload,
                        "created_at": event.created_at.isoformat(),
                    }
                ],
                prefer="return=minimal",
            )
            return True

        return bool(self._safe("save_audit", operation, False))

    def list_audits(self, case_id: str) -> list[AuditEvent]:
        def operation() -> list[AuditEvent]:
            case_uuid = self._case_uuid(case_id)
            if not case_uuid:
                return []
            rows = self._request(
                "audit_logs",
                params={
                    "case_id": f"eq.{case_uuid}",
                    "select": "created_at,event_type,payload",
                    "order": "created_at.asc",
                },
            )
            events: list[AuditEvent] = []
            for row in rows:
                payload = dict(row.get("payload") or {})
                event_id = str(payload.pop("_event_id", f"audit_{case_uuid[:8]}"))
                actor = str(payload.pop("_actor", "system"))
                created_at = row.get("created_at") or datetime.now(timezone.utc).isoformat()
                events.append(
                    AuditEvent(
                        event_id=event_id,
                        case_id=case_id,
                        event_type=str(row.get("event_type", "")),
                        actor=actor,
                        created_at=created_at,
                        payload=payload,
                    )
                )
            return events

        return self._safe("list_audits", operation, [])
