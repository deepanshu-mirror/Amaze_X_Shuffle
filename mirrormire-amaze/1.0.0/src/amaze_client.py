"""AMaze REST API client for the Shuffle python-app.

Thin, dependency-light client for the AMaze (mirrormire-amaze) platform REST
API v3 exposed by ``amaze-core``. Every method maps 1:1 to a verified
endpoint. Endpoints were verified against
``mirrormire-amaze/services/amaze-core/app/routers/``.

Authentication is a bearer token (JWT or API token) passed as ``Authorization:
Bearer <token>``. All endpoints require it.

Example usage::

    from amaze_client import AmazeClient

    client = AmazeClient("https://amaze.example.com/api/v3", "jwt-token-here")
    tickets = client.list_tickets(status="OPEN", limit=10)
    ticket  = client.get_ticket("3fa85f64-5717-4562-b3fc-2c963f66afa6")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import requests

DEFAULT_TIMEOUT_SECONDS = 20

USER_AGENT = "amaze-shuffle/1.0.0"


class AmazeAPIError(Exception):
    """Raised when the AMaze API returns an HTTP error status (>= 400).

    Carries the HTTP ``status_code`` so Shuffle workflows can branch on
    authentication/authorization failures (401/403) vs server errors (5xx).

    Attributes:
        status_code: The HTTP status code returned by the AMaze API.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class AmazeClient:
    """Thin REST client for the AMaze deception platform API v3.

    Every public method maps 1:1 to a verified AMaze API endpoint. Query
    parameters that are ``None`` or empty strings are automatically stripped
    from the request.

    Attributes:
        base_url: Full AMaze API base URL including the API path, e.g.
            ``https://amaze.example.com/api/v3``. No prefix or suffix is
            added — request paths are appended directly to this URL.
        timeout: HTTP request timeout in seconds. Default 20.
        verify: TLS certificate verification. ``True`` by default; set to
            ``False`` only for self-signed / on-prem instances. Shuffle
            passes this as a string (``"true"`` / ``"false"``) which is
            normalised automatically.
        headers: Default HTTP headers sent with every request (bearer auth,
            JSON content-type, User-Agent).
        logger: A :class:`logging.Logger` instance for debug-level request
            logging. When ``None`` (default), logging is suppressed.
    """

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        verify: Optional[bool] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initialise an AMaze API client.

        Args:
            base_url: Full AMaze API base URL including the API path, e.g.
                ``https://amaze.example.com/api/v3``. Trailing slashes are
                stripped automatically; request paths are appended directly
                (no additional version prefix is added).
            bearer_token: JWT or API token for the AMaze REST API.
            timeout: HTTP request timeout in seconds. Defaults to
                :data:`DEFAULT_TIMEOUT_SECONDS` (20).
            verify: TLS certificate verification. When ``None`` (default)
                or ``True``, certificates are verified. Pass ``False`` (or
                the string ``"false"``, as Shuffle does) to skip
                verification for self-signed instances.
            logger: Optional :class:`logging.Logger` for debug-level
                request/response logging. When ``None``, no logging is
                performed.
        """
        # Normalise the base URL: strip whitespace/trailing slashes and
        # default to https:// when no scheme is supplied. Shuffle workflows
        # and CLI users frequently pass a bare host (e.g.
        # "amaze.example.com/api/v3"), which would otherwise surface as a
        # confusing requests.exceptions.MissingSchema at request time.
        base_url = (base_url or "").strip()
        if base_url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", base_url):
            base_url = f"https://{base_url}"
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger

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
            "User-Agent": USER_AGENT,
        }

    # ── Low-level helpers ──────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        *,
        base_url: Optional[str] = None,
    ) -> Any:
        """Execute an HTTP request against the AMaze API.

        Args:
            method: HTTP method (``GET``, ``POST``, ``PUT``, ``DELETE``).
            path: URL path appended directly to ``base_url``, e.g.
                ``/tickets``.
            params: Query-string parameters. ``None`` and empty-string
                values are automatically stripped.
            json_body: JSON-serialisable request body (for ``PUT`` /
                ``POST``).
            base_url: Optional override for ``self.base_url``. Used when
                an endpoint lives under a different API version (e.g.
                ``/api/v1/…`` instead of ``/api/v3/…``).

        Returns:
            Parsed JSON response body, or ``None`` for 204 No Content.

        Raises:
            AmazeAPIError: If the API returns an HTTP status >= 400.
        """
        url_base = base_url or self.base_url
        url = f"{url_base}{path}"
        cleaned = {
            k: v for k, v in (params or {}).items() if v is not None and v != ""
        }

        if self.logger is not None:
            self.logger.debug(
                "AMaze API request: %s %s (params=%s, body=%s)",
                method, url, cleaned or None, json_body or None,
            )

        response = requests.request(
            method,
            url,
            headers=self.headers,
            params=cleaned,
            json=json_body,
            timeout=self.timeout,
            verify=self.verify,
        )

        if self.logger is not None:
            self.logger.debug(
                "AMaze API response: %s %s → %s",
                method, path, response.status_code,
            )

        if response.status_code >= 400:
            raise AmazeAPIError(
                response.status_code,
                f"HTTP {response.status_code} {response.reason} on "
                f"{method} {path}: {response.text[:500]}",
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
        """List and filter AMaze incident tickets (actionable alerts).

        ``GET /api/v3/tickets``

        Args:
            status: Ticket status filter (``OPEN`` | ``IN_PROGRESS`` |
                ``CLOSED``).
            ip: Source IP prefix or exact match, e.g. ``185.220.101.34``.
            protocol: Exact protocol, case-insensitive (``ssh``,
                ``http``, …).
            ttp: MITRE TTP prefix (``T1110`` matches ``T1110.001``).
            country: Country substring, case-insensitive (e.g. ``"RU"``).
            min_score: Minimum threat score (0–100).
            q: Free-text search across title and description.
            from_dt: Created at or after (ISO 8601).
            to_dt: Created at or before (ISO 8601).
            site_id: Filter by site UUID.
            limit: Page size (default 200, max 1000).
            offset: Skip this many rows (pagination).

        Returns:
            List of ticket objects.
        """
        return self._request(
            "GET",
            "/tickets",
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
        """Retrieve a specific AMaze ticket by ID.

        ``GET /api/v3/tickets/{ticket_id}``

        Args:
            ticket_id: Ticket UUID.

        Returns:
            Ticket object with full enrichment details and remediation
            text.
        """
        return self._request("GET", f"/tickets/{ticket_id}")

    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        description: Optional[str] = None,
        remediation: Optional[str] = None,
    ) -> Any:
        """Update an AMaze ticket status, description and/or remediation.

        ``PUT /api/v3/tickets/{ticket_id}``

        Args:
            ticket_id: Ticket UUID.
            status: Ticket status (``OPEN`` | ``IN_PROGRESS`` |
                ``CLOSED``).
            description: New ticket description.
            remediation: Recommended remediation text.

        Returns:
            Updated ticket object.

        Raises:
            ValueError: If none of ``status``, ``description``, or
                ``remediation`` is provided.
        """
        body: Dict[str, Any] = {}
        if status is not None:
            body["status"] = status
        if description is not None:
            body["description"] = description
        if remediation is not None:
            body["remediation"] = remediation
        if not body:
            raise ValueError(
                "At least one of status/description/remediation is required"
            )
        return self._request("PUT", f"/tickets/{ticket_id}", json_body=body)

    def delete_ticket(self, ticket_id: str) -> Any:
        """Delete an AMaze ticket (admin only on the API).

        ``DELETE /api/v3/tickets/{ticket_id}``

        Args:
            ticket_id: Ticket UUID.

        Returns:
            ``None`` (204 No Content).
        """
        return self._request("DELETE", f"/tickets/{ticket_id}")

    def list_ticket_dispatches(self, ticket_id: str) -> Any:
        """Full integration dispatch history for one ticket, newest first.

        ``GET /api/v3/tickets/{ticket_id}/dispatches``

        Args:
            ticket_id: Ticket UUID.

        Returns:
            List of dispatch objects with integration name, status,
            attempts, and timestamps.
        """
        return self._request("GET", f"/tickets/{ticket_id}/dispatches")

    def retry_ticket_dispatch(self, ticket_id: str, dispatch_id: str) -> Any:
        """Admin-only: re-fire a failed dispatch using the original event
        payload.

        ``POST /api/v3/tickets/{ticket_id}/dispatches/{dispatch_id}/retry``

        Args:
            ticket_id: Ticket UUID.
            dispatch_id: Dispatch UUID.

        Returns:
            Dispatch object with ``status`` and ``attempt`` counter.
        """
        return self._request(
            "POST", f"/tickets/{ticket_id}/dispatches/{dispatch_id}/retry"
        )

    # ── Integrations ───────────────────────────────────────────────────────

    def test_integration(self, integration_id: str) -> Any:
        """Fire a synthetic Rich Alert at an integration and record the
        attempt (admin only).

        ``POST /api/v3/integrations/{integration_id}/test``

        Args:
            integration_id: Integration UUID.

        Returns:
            Test result object with ``status`` and ``latency_ms``.
        """
        return self._request("POST", f"/integrations/{integration_id}/test")

    # ── Approvals (HITL) ───────────────────────────────────────────────────

    def list_approvals(
        self,
        status: Optional[str] = None,
        site_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        """List pending approval requests for outbound dispatches.

        ``GET /api/v3/approvals``

        Args:
            status: Approval status filter (``pending`` | ``approved`` |
                ``rejected`` | ``expired``).
            site_id: Filter by site UUID.
            ticket_id: Filter to approvals whose dispatch belongs to this
                ticket.
            limit: Result limit (default 200, max 1000).

        Returns:
            List of approval objects.
        """
        return self._request(
            "GET",
            "/approvals",
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
        """Paginated external-network SCA logs.

        ``GET /api/v3/external/logs``

        Args:
            protocol: Protocol filter (``ssh``, ``http``, …).
            ip: Source IP filter.
            country: Country filter (e.g. ``"RU"``).
            site_id: Filter by site UUID.
            page: Page number (default 1).
            limit: Page size (default 50, max 500).
            sort_by: Sort column (``timestamp`` | ``threat_score`` |
                ``src_ip`` | ``country`` | ``protocol`` | ``sca_id`` |
                ``sca_name`` | ``username``).
            sort_order: ``asc`` or ``desc`` (default ``desc``).

        Returns:
            Paginated result with ``items``, ``total``, ``page``, and
            ``limit``.
        """
        return self._request(
            "GET",
            "/external/logs",
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
        """Paginated internal-network SCA logs.

        ``GET /api/v3/internal/logs``

        Args:
            protocol: Protocol filter (e.g. ``"rdp"``).
            ip: Source IP filter.
            site_id: Filter by site UUID.
            page: Page number (default 1).
            limit: Page size (default 50, max 500).
            sort_by: Sort column.
            sort_order: ``asc`` or ``desc``.

        Returns:
            Paginated result with ``items``, ``total``, ``page``, and
            ``limit``.
        """
        return self._request(
            "GET",
            "/internal/logs",
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
        """Paginated OT-network SCA logs (Modbus, DNP3, S7, …).

        ``GET /api/v3/ot/logs``

        Args:
            protocol: Protocol filter (``modbus``, ``dnp3``, ``s7``, …).
            ip: Source IP filter.
            site_id: Filter by site UUID.
            page: Page number (default 1).
            limit: Page size (default 50, max 500).
            sort_by: Sort column.
            sort_order: ``asc`` or ``desc``.

        Returns:
            Paginated result with ``items``, ``total``, ``page``, and
            ``limit``.
        """
        return self._request(
            "GET",
            "/ot/logs",
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
        """Paginated Active-Directory (AD server) SCA logs.

        ``GET /api/v3/active-directory/logs``

        Args:
            protocol: Protocol filter (e.g. ``"ldap"``).
            ip: Source IP filter.
            site_id: Filter by site UUID.
            page: Page number (default 1).
            limit: Page size (default 50, max 500).
            sort_by: Sort column.
            sort_order: ``asc`` or ``desc``.

        Returns:
            Paginated result with ``items``, ``total``, ``page``, and
            ``limit``.
        """
        return self._request(
            "GET",
            "/active-directory/logs",
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
        """Paginated AI-threats (AI-deception layer) logs.

        ``GET /api/v3/ai-threats/logs``

        Args:
            protocol: Protocol filter (e.g. ``"ai-agent"``).
            ip: Source IP filter.
            site_id: Filter by site UUID.
            page: Page number (default 1).
            limit: Page size (default 50, max 500).
            sort_by: Sort column.
            sort_order: ``asc`` or ``desc``.

        Returns:
            Paginated result with ``items``, ``total``, ``page``, and
            ``limit``.
        """
        return self._request(
            "GET",
            "/ai-threats/logs",
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
        ip: str,
        site_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        """Paginated multi-stage attack trails (IP attack path).

        ``GET /api/v3/attack-path``

        Args:
            ip: Source IP address to trace the attack path for
                (required), e.g. ``"185.220.101.34"``.
            site_id: Filter by site UUID.
            limit: Page size.

        Returns:
            Paginated result with ``items`` (each containing ``src_ip``,
            ``hops``, ``protocols``, ``severity``) and ``total``.
        """
        return self._request(
            "GET",
            "/attack-path",
            params={"ip": ip, "site_id": site_id, "limit": limit},
        )

    # ── Sites / context / enrichment ───────────────────────────────────────

    def list_sites(self) -> Any:
        """List sites the caller is authorised to see.

        ``GET /api/v3/sites``

        Returns:
            List of site objects (``id``, ``name``, ``tenant_id``).
        """
        return self._request("GET", "/sites")

    def get_site_summary(self, site_id: str) -> Any:
        """Summary stats for a single site.

        ``GET /api/v3/sites/{site_id}/summary``

        Args:
            site_id: Site UUID.

        Returns:
            Site summary object with ``total_events``, ``open_tickets``,
            ``critical_assets``.
        """
        return self._request("GET", f"/sites/{site_id}/summary")

    def check_ip_reputation(self, ip: str, source: str = "ipqs") -> Any:
        """Check IP reputation via the AMaze proxy.

        ``POST /api/v1/reputation/{source}``

        .. note::

           The reputation endpoint lives under ``/api/v1``, not
           ``/api/v3``. The client automatically replaces the version
           prefix in ``base_url`` for this call. If your AMaze instance
           is behind the Mirrormire dashboard BFF, you may need an
           additional ``/api/v1/…`` pass-through route in the BFF, or
           point ``base_url`` directly at the AMaze core (e.g.
           ``http://core:8000/api/v3``).

        Supports IPQS, AbuseIPDB, and VirusTotal lookups proxied through
        the AMaze API.

        Args:
            ip: IP address to check, e.g. ``"185.220.101.34"``.
            source: Reputation provider — one of ``"ipqs"``,
                ``"abuseipdb"``, ``"virustotal"``. Default ``"ipqs"``.

        Returns:
            Reputation result object with ``ip``, ``source``,
            ``fraud_score``, ``is_proxy``, ``risk``.
        """
        # Reputation lives under /api/v1, not /api/v3.
        v1_base = self.base_url.replace("/api/v3", "/api/v1")
        return self._request(
            "POST", f"/reputation/{source}", json_body={"ip": ip},
            base_url=v1_base,
        )

    def list_protocols(self) -> Any:
        """List active protocols tracked by the platform.

        ``GET /api/v3/system/protocols``

        Returns:
            Dict with ``protocols`` key containing the list of active
            protocol names, e.g.
            ``{"protocols": ["ssh", "rdp", "http", "mysql", "modbus", …]}``.
        """
        return self._request("GET", "/system/protocols")

    def get_alert_config(self) -> Any:
        """Get the latest high-threat system alerts.

        ``GET /api/v3/system/alert``

        Returns:
            Dict with ``alerts`` (list of alert objects with
            ``threat_score >= 70``) and ``count``, e.g.
            ``{"alerts": […], "count": 3}``.
        """
        return self._request("GET", "/system/alert")

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
        """List the immutable audit log (admin/auditor).

        ``GET /api/v3/audit-log``

        Args:
            limit: Result limit (default 100, max 500).
            offset: Skip this many rows.
            actor: Filter by actor email, e.g.
                ``"analyst@example.com"``.
            action: Filter by exact action name, e.g.
                ``"ticket.update"``.
            from_dt: Only entries at/after this time (ISO 8601).
            to_dt: Only entries at/before this time (ISO 8601).

        Returns:
            Paginated audit log with ``items`` and ``total``.
        """
        return self._request(
            "GET",
            "/audit-log",
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
        """List report runs (scheduled/signed CISO & board reports).

        ``GET /api/v3/reports/runs``

        Args:
            schedule_id: Filter by report schedule UUID.
            limit: Result limit (default 50, max 200).

        Returns:
            List of report run objects with ``status``, ``period_start``/
            ``period_end``, ``created_at``, and ``completed_at``.
        """
        return self._request(
            "GET",
            "/reports/runs",
            params={"schedule_id": schedule_id, "limit": limit},
        )

    def get_report_run(self, run_id: str) -> Any:
        """Get details for a single report run.

        ``GET /api/v3/reports/runs/{run_id}``

        Args:
            run_id: Report run UUID.

        Returns:
            Report run object with ``status``, ``pdf_sha256``,
            ``signature``, ``summary_json``, and ``dispatch_history``.
            (The signed PDF itself is fetched from
            ``/api/v3/reports/runs/{run_id}/pdf``.)
        """
        return self._request("GET", f"/reports/runs/{run_id}")
