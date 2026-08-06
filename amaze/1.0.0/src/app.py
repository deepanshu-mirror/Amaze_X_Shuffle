"""AMaze — Shuffle (SOAR) python-app.

Entry point for the AMaze deception platform integration inside Shuffle.
Each public method below is an *action* that maps 1:1 to an entry in
``api.yaml`` (same name + argument list). Shared credentials (``base_url``,
``bearer_token``) are declared under ``authentication:`` in ``api.yaml`` and
injected into every action by Shuffle.

Runs in three modes:
  * Inside the Shuffle SDK container — ``AppBase.run()`` dispatches actions.
  * Locally with ``shuffle_sdk`` installed:
        python src/app.py --standalone --action=list_tickets \\
            base_url=http://localhost:8000 bearer_token=TOKEN
  * Locally with no SDK (pure CLI):
        python src/app.py list_tickets --base-url ... --bearer-token ...
"""

from __future__ import annotations

import inspect
import json
import logging
import sys
from argparse import ArgumentParser
from typing import Any, Dict, Optional

# The AppBase import chain keeps the app working inside the Shuffle SDK image
# (walkoff_app_sdk / shuffle_sdk / app_base) AND falling back to a plain CLI
# when no SDK is installed locally.
try:
    from walkoff_app_sdk.app_base import AppBase  # type: ignore
    # NOTE: walkoff_app_sdk is only resolvable inside the Shuffle SDK image.
except ImportError:  # pragma: no cover - environment dependent
    try:
        from shuffle_sdk import AppBase
    except ImportError:
        try:
            from app_base import AppBase  # type: ignore
        except ImportError:
            AppBase = object

from amaze_client import AmazeClient


class _NoArgFriendlyParser(ArgumentParser):
    """ArgumentParser that exits cleanly (0) on a bare no-arg invocation.

    Upstream's ``analyze.py`` smoke-tests every app by running
    ``python3 src/app.py`` with no arguments and judges the result by its
    output: a non-empty STDOUT is treated as a successful run, while anything
    on STDERR (other than a ModuleNotFoundError) is reported as a broken app.
    So a bare invocation prints help to STDOUT and exits 0. Real CLI errors
    still behave normally (exit 2).
    """

    def error(self, message: str) -> None:  # pragma: no cover - CLI only
        if len(sys.argv) <= 1:
            self.print_help()  # to STDOUT, so analyze.py's smoke run passes
            raise SystemExit(0)
        super().error(message)


class AMaze(AppBase):
    __version__ = "1.0.0"
    app_name = "amaze"  # must match "name" in api.yaml

    def __init__(self, redis=None, logger=None, console_logger=None) -> None:
        if AppBase is not object:
            try:
                super().__init__(redis, logger, console_logger)
            except (TypeError, AttributeError):
                # Some SDK builds raise when constructed without a logger
                # (e.g. shuffle_sdk's __init__ calls logger.addHandler on a
                # None logger) or with a different __init__ signature. Fall
                # back to a no-arg init and keep going.
                try:
                    super().__init__()
                except (TypeError, AttributeError):
                    pass
        # Always guarantee a minimal logging surface for CLI/local runs.
        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(self.__class__.__name__)
        if not hasattr(self, "console_logger"):
            self.console_logger = self.logger

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _client(
        base_url: str, bearer_token: str, verify: Optional[bool] = None
    ) -> AmazeClient:
        return AmazeClient(
            base_url=base_url, bearer_token=bearer_token, verify=verify
        )

    # ── Tickets ────────────────────────────────────────────────────────────

    def list_tickets(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
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
        return self._client(base_url, bearer_token, verify).list_tickets(
            status=status,
            ip=ip,
            protocol=protocol,
            ttp=ttp,
            country=country,
            min_score=min_score,
            q=q,
            from_dt=from_dt,
            to_dt=to_dt,
            site_id=site_id,
            limit=limit,
            offset=offset,
        )

    def get_ticket(
        self,
        base_url: str,
        bearer_token: str,
        ticket_id: str,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_ticket(ticket_id)

    def update_ticket(
        self,
        base_url: str,
        bearer_token: str,
        ticket_id: str,
        verify: Optional[bool] = None,
        status: Optional[str] = None,
        description: Optional[str] = None,
        remediation: Optional[str] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).update_ticket(
            ticket_id=ticket_id,
            status=status,
            description=description,
            remediation=remediation,
        )

    def delete_ticket(
        self,
        base_url: str,
        bearer_token: str,
        ticket_id: str,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).delete_ticket(ticket_id)

    def list_ticket_dispatches(
        self,
        base_url: str,
        bearer_token: str,
        ticket_id: str,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).list_ticket_dispatches(
            ticket_id
        )

    def retry_ticket_dispatch(
        self,
        base_url: str,
        bearer_token: str,
        ticket_id: str,
        dispatch_id: str,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).retry_ticket_dispatch(
            ticket_id, dispatch_id
        )

    # ── Integrations ───────────────────────────────────────────────────────

    def test_integration(
        self,
        base_url: str,
        bearer_token: str,
        integration_id: str,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).test_integration(
            integration_id
        )

    # ── Approvals (HITL) ───────────────────────────────────────────────────

    def list_approvals(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        status: Optional[str] = None,
        site_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).list_approvals(
            status=status,
            site_id=site_id,
            ticket_id=ticket_id,
            limit=limit,
        )

    # ── Logs / detection data ──────────────────────────────────────────────

    def get_external_logs(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        country: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_external_logs(
            protocol=protocol,
            ip=ip,
            country=country,
            site_id=site_id,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_internal_logs(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_internal_logs(
            protocol=protocol,
            ip=ip,
            site_id=site_id,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_ot_logs(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_ot_logs(
            protocol=protocol,
            ip=ip,
            site_id=site_id,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_ad_logs(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_ad_logs(
            protocol=protocol,
            ip=ip,
            site_id=site_id,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_ai_threats_logs(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        protocol: Optional[str] = None,
        ip: Optional[str] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_ai_threats_logs(
            protocol=protocol,
            ip=ip,
            site_id=site_id,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_attack_path(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        site_id: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_attack_path(
            site_id=site_id,
            page=page,
            limit=limit,
        )

    # ── Sites / context / enrichment ───────────────────────────────────────

    def list_sites(
        self, base_url: str, bearer_token: str, verify: Optional[bool] = None
    ) -> Any:
        return self._client(base_url, bearer_token, verify).list_sites()

    def get_site_summary(
        self,
        base_url: str,
        bearer_token: str,
        site_id: str,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_site_summary(site_id)

    def check_ip_reputation(
        self,
        base_url: str,
        bearer_token: str,
        ip: str,
        source: Optional[str] = None,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).check_ip_reputation(
            ip=ip, source=source or "ipqs"
        )

    def list_protocols(
        self, base_url: str, bearer_token: str, verify: Optional[bool] = None
    ) -> Any:
        return self._client(base_url, bearer_token, verify).list_protocols()

    def get_alert_config(
        self, base_url: str, bearer_token: str, verify: Optional[bool] = None
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_alert_config()

    # ── Audit & reports ────────────────────────────────────────────────────

    def list_audit_log(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        from_dt: Optional[str] = None,
        to_dt: Optional[str] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).list_audit_log(
            limit=limit,
            offset=offset,
            actor=actor,
            action=action,
            from_dt=from_dt,
            to_dt=to_dt,
        )

    def list_report_runs(
        self,
        base_url: str,
        bearer_token: str,
        verify: Optional[bool] = None,
        schedule_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).list_report_runs(
            schedule_id=schedule_id,
            limit=limit,
        )

    def get_report_run(
        self,
        base_url: str,
        bearer_token: str,
        run_id: str,
        verify: Optional[bool] = None,
    ) -> Any:
        return self._client(base_url, bearer_token, verify).get_report_run(run_id)

    # ── Runner ─────────────────────────────────────────────────────────────

    @classmethod
    def run(cls) -> None:
        """Prefer the SDK runner when available; otherwise use the plain CLI."""
        if AppBase is not object and hasattr(AppBase, "run"):
            super().run()
            return
        cls._run_cli()

    @classmethod
    def _run_cli(cls) -> None:
        """Minimal standalone CLI for local testing without the Shuffle SDK.

        Usage: python src/app.py list_tickets --base-url http://localhost:8000 \\
                    --bearer-token TOKEN [--status OPEN] ...
        """
        parser = _NoArgFriendlyParser(
            description="AMaze Shuffle app — local CLI runner"
        )
        parser.add_argument("action", help="Action to execute")
        parser.add_argument("--base-url", required=True, help="AMaze API base URL")
        parser.add_argument("--bearer-token", required=True, help="AMaze bearer token")
        parser.add_argument("--ticket-id", help="Ticket UUID")
        parser.add_argument("--integration-id", help="Integration UUID")
        parser.add_argument("--dispatch-id", help="Dispatch UUID")
        parser.add_argument("--run-id", help="Report run UUID")
        parser.add_argument("--site-id", help="Site UUID filter")
        parser.add_argument("--status", help="Ticket/approval status filter")
        parser.add_argument("--ip", help="Source IP filter")
        parser.add_argument("--protocol", help="Protocol filter")
        parser.add_argument("--ttp", help="TTP filter")
        parser.add_argument("--country", help="Country filter")
        parser.add_argument("--min-score", type=int, help="Minimum threat score")
        parser.add_argument("--q", help="Free-text search")
        parser.add_argument("--from-dt", help="Created at/after (ISO 8601)")
        parser.add_argument("--to-dt", help="Created at/before (ISO 8601)")
        parser.add_argument("--limit", type=int, help="Result limit")
        parser.add_argument("--offset", type=int, help="Result offset")
        parser.add_argument("--page", type=int, help="Page number")
        parser.add_argument("--description", help="Ticket description")
        parser.add_argument("--remediation", help="Ticket remediation text")
        parser.add_argument("--source", help="Reputation source: ipqs|abuseipdb|virustotal")
        parser.add_argument("--actor", help="Audit filter by actor")
        parser.add_argument("--action-filter", dest="action_filter", help="Audit filter by action")
        parser.add_argument("--schedule-id", help="Report schedule filter")
        parser.add_argument("--sort-by", help="Log sort column")
        parser.add_argument("--sort-order", help="Log sort order (asc|desc)")
        parser.add_argument(
            "--verify", help="TLS verification (true|false), default true"
        )
        args = parser.parse_args()

        app = cls()
        action = getattr(app, args.action, None)
        if action is None:
            sys.exit(f"Unknown action: {args.action}")

        kwargs: Dict[str, Any] = {
            "base_url": args.base_url,
            "bearer_token": args.bearer_token,
            "ticket_id": args.ticket_id,
            "integration_id": args.integration_id,
            "dispatch_id": args.dispatch_id,
            "run_id": args.run_id,
            "site_id": args.site_id,
            "status": args.status,
            "ip": args.ip,
            "protocol": args.protocol,
            "ttp": args.ttp,
            "country": args.country,
            "min_score": args.min_score,
            "q": args.q,
            "from_dt": args.from_dt,
            "to_dt": args.to_dt,
            "limit": args.limit,
            "offset": args.offset,
            "page": args.page,
            "description": args.description,
            "remediation": args.remediation,
            "source": args.source,
            "actor": args.actor,
            # --action-filter targets the `action` kwarg (list_audit_log).
            "action": args.action_filter,
            "schedule_id": args.schedule_id,
            "sort_by": args.sort_by,
            "sort_order": args.sort_order,
            "verify": args.verify,
        }
        # Only pass arguments the action actually accepts.
        sig = inspect.signature(action)
        accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        result = action(**accepted)
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")


if __name__ == "__main__":
    AMaze.run()
