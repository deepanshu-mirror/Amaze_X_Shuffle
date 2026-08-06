"""AMaze REST API client for the Shuffle python-app.

Thin, dependency-light client for the AMaze (mirrormire-amaze) platform REST
API v3 exposed by ``amaze-core``. Every method maps 1:1 to a verified
endpoint. Endpoints were verified against
``mirrormire-amaze/services/amaze-core/app/routers/``.

Authentication is a bearer token (JWT or API token) passed as ``Authorization:
Bearer <token>``. All endpoints require it.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

DEFAULT_TIMEOUT_SECONDS = 20


class AmazeAPIError(RuntimeError):
    """Raised when the AMaze API returns an error status (>= 400).

    Carries the HTTP ``status_code`` so Shuffle workflows can branch on
    authentication/authorization failures (401/403) vs other errors (5xx).
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class AmazeClient:
    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        verify: Optional[bool] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Shuffle passes action parameters as strings, so normalise
        # "true"/"false"/"1"/"0" to a real bool. Defaults to True.
        if verify is None:
            self.verify = True
        elif isinstance(verify, str):
            self.verify = verify.strip().lower() in ("1", "true", "yes", "on")
        else:
            self.verify = bool(verify)
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ── Low-level helpers ──────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        cleaned = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        response = requests.request(
            method,
            url,
            headers=self.headers,
            params=cleaned,
            json=json_body,
            timeout=self.timeout,
            verify=self.verify,
        )
        if response.status_code >= 400:
            raise AmazeAPIError(
                response.status_code,
                f"HTTP {response.status_code} {response.reason} on {method} {path}: "
                f"{response.text[:500]}",
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # ── Tickets ────────────────────────────────────────────────────────────

    def list_tickets(
        self,
        status: Optional[str] = None,
        ip: Optional[str] = None,
        protocol: Optional[str] = None,
        ttp: Optional[str] = None,
        country: Optional[str] = None,
        min_score: Optional[int] = None,
        q: Optional[str] = None,
        from_dt: Optional[str] = None,
        to_dt: Optional[str] = None,
        site_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/tickets/",
            params={
                "status": status,
                "ip": ip,
                "protocol": protocol,
                "ttp": ttp,
                "country": country,
                "min_score": min_score,
                "q": q,
                "from": from_dt,
                "to": to_dt,
                "site_id": site_id,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_ticket(self, ticket_id: str) -> Any:
        return self._request("GET", f"/api/v3/tickets/{ticket_id}")

    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        description: Optional[str] = None,
        remediation: Optional[str] = None,
    ) -> Any:
        body: Dict[str, Any] = {}
        if status is not None:
            body["status"] = status
        if description is not None:
            body["description"] = description
        if remediation is not None:
            body["remediation"] = remediation
        if not body:
            raise ValueError("At least one of status/description/remediation is required")
        return self._request("PUT", f"/api/v3/tickets/{ticket_id}", json_body=body)

    def delete_ticket(self, ticket_id: str) -> Any:
        return self._request("DELETE", f"/api/v3/tickets/{ticket_id}")

    def list_ticket_dispatches(self, ticket_id: str) -> Any:
        return self._request("GET", f"/api/v3/tickets/{ticket_id}/dispatches")

    def retry_ticket_dispatch(self, ticket_id: str, dispatch_id: str) -> Any:
        return self._request(
            "POST", f"/api/v3/tickets/{ticket_id}/dispatches/{dispatch_id}/retry"
        )

    # ── Integrations ───────────────────────────────────────────────────────

    def test_integration(self, integration_id: str) -> Any:
        return self._request("POST", f"/api/v3/integrations/{integration_id}/test")

    # ── Approvals (HITL) ───────────────────────────────────────────────────

    def list_approvals(
        self,
        status: Optional[str] = None,
        site_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/approvals/",
            params={
                "status": status,
                "site_id": site_id,
                "ticket_id": ticket_id,
                "limit": limit,
            },
        )

    # ── Logs / detection data ──────────────────────────────────────────────

    def get_external_logs(
        self,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        country: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/external/logs",
            params={
                "protocol": protocol,
                "ip": ip,
                "country": country,
                "site_id": site_id,
                "page": page,
                "limit": limit,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )

    def get_internal_logs(
        self,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/internal/logs",
            params={
                "protocol": protocol,
                "ip": ip,
                "site_id": site_id,
                "page": page,
                "limit": limit,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )

    def get_ot_logs(
        self,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/ot/logs",
            params={
                "protocol": protocol,
                "ip": ip,
                "site_id": site_id,
                "page": page,
                "limit": limit,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )

    def get_ad_logs(
        self,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/active-directory/logs",
            params={
                "protocol": protocol,
                "ip": ip,
                "site_id": site_id,
                "page": page,
                "limit": limit,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )

    def get_ai_threats_logs(
        self,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/ai-threats/logs",
            params={
                "protocol": protocol,
                "ip": ip,
                "site_id": site_id,
                "page": page,
                "limit": limit,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )

    def get_attack_path(
        self,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/attack-path",
            params={"site_id": site_id, "page": page, "limit": limit},
        )

    # ── Sites / context / enrichment ───────────────────────────────────────

    def list_sites(self) -> Any:
        return self._request("GET", "/api/v3/sites/")

    def get_site_summary(self, site_id: str) -> Any:
        return self._request("GET", f"/api/v3/sites/{site_id}/summary")

    def check_ip_reputation(self, ip: str, source: str = "ipqs") -> Any:
        """POST /api/reputation/{source} — source in {ipqs, abuseipdb, virustotal}."""
        return self._request(
            "POST", f"/api/reputation/{source}", json_body={"ip": ip}
        )

    def list_protocols(self) -> Any:
        return self._request("GET", "/api/v3/system/protocols")

    def get_alert_config(self) -> Any:
        return self._request("GET", "/api/v3/system/alert")

    # ── Audit & reports ────────────────────────────────────────────────────

    def list_audit_log(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        from_dt: Optional[str] = None,
        to_dt: Optional[str] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/audit-log/",
            params={
                "limit": limit,
                "offset": offset,
                "actor": actor,
                "action": action,
                "from": from_dt,
                "to": to_dt,
            },
        )

    def list_report_runs(
        self,
        schedule_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return self._request(
            "GET",
            "/api/v3/reports/runs",
            params={"schedule_id": schedule_id, "limit": limit},
        )

    def get_report_run(self, run_id: str) -> Any:
        return self._request("GET", f"/api/v3/reports/runs/{run_id}")
