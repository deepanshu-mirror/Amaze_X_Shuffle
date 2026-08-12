# AMaze

AMaze deception platform (Mirrormire AI) integration for Shuffle. Query and operate deception-detection tickets, approvals, logs, sites, IP reputation and audit/reporting via the AMaze REST APIs.

[![AMaze Shuffle App](amaze.png?raw=true)](amaze.png?raw=true)

## Requirements

- AMaze API base URL (e.g. `https://dashboard.mirrormire.ai/api/v3` — include the `/api/v3` path)
- Bearer token (JWT or API token) for AMaze API access
- TLS verification can be disabled for self-signed / on-prem instances

## Note

- **Admin-only actions:** `delete_ticket`, `retry_ticket_dispatch`, `test_integration`, and `list_audit_log` require an **admin** role token. All other actions work with analyst, auditor, or admin roles.
- **TLS:** Set `verify` to `false` in the authentication block if your AMaze instance uses a self-signed certificate.
- **Reputation endpoint:** `check_ip_reputation` calls AMaze's `/api/v1/reputation/{source}` (not `/api/v3`). If your `base_url` points through the Mirrormire dashboard BFF (e.g. `https://dashboard.mirrormire.ai/api/v3`), the BFF must have a matching `/api/v1/…` pass-through route, or you must point `base_url` directly at the AMaze core (e.g. `http://core:8000/api/v3`).

## Actions

1. **list_tickets** — List and filter AMaze incident tickets (actionable alerts).
   - **status** : Ticket status filter (OPEN | IN_PROGRESS | CLOSED)
   - **ip** : Source IP prefix or exact match
   - **protocol** : Exact protocol, case-insensitive (ssh, http, …)
   - **ttp** : MITRE TTP prefix (T1110 matches T1110.001)
   - **country** : Country substring, case-insensitive
   - **min_score** : Minimum threat score (0–100)
   - **q** : Free-text search across title and description
   - **from_dt** : Created at or after (ISO 8601)
   - **to_dt** : Created at or before (ISO 8601)
   - **site_id** : Filter by site UUID
   - **limit** : Page size (default 200, max 1000)
   - **offset** : Skip this many rows (pagination)

2. **get_ticket** — Retrieve a specific AMaze ticket by ID.
   - **ticket_id** : Ticket UUID (required)

3. **update_ticket** — Update an AMaze ticket status, description and/or remediation.
   - **ticket_id** : Ticket UUID (required)
   - **status** : Ticket status (OPEN | IN_PROGRESS | CLOSED)
   - **description** : New ticket description
   - **remediation** : Recommended remediation text

4. **delete_ticket** — Delete an AMaze ticket (admin only).
   - **ticket_id** : Ticket UUID (required)

5. **list_ticket_dispatches** — Integration dispatch history for one ticket, newest first.
   - **ticket_id** : Ticket UUID (required)

6. **retry_ticket_dispatch** — Re-fire a failed dispatch (admin only).
   - **ticket_id** : Ticket UUID (required)
   - **dispatch_id** : Dispatch UUID (required)

7. **test_integration** — Fire a synthetic Rich Alert at an integration (admin only).
   - **integration_id** : Integration UUID (required)

8. **list_approvals** — List pending approval requests for outbound dispatches.
   - **status** : Approval status filter (pending | approved | rejected | expired)
   - **site_id** : Filter by site UUID
   - **ticket_id** : Filter by ticket UUID
   - **limit** : Result limit (default 200, max 1000)

9. **get_external_logs** — Paginated external-network SCA logs.
   - **protocol** : Protocol filter (ssh, http, …)
   - **ip** : Source IP filter
   - **country** : Country filter
   - **site_id** : Filter by site UUID
   - **page** : Page number (default 1)
   - **limit** : Page size (default 50, max 500)
   - **sort_by** : Sort column (timestamp | threat_score | src_ip | …)
   - **sort_order** : asc | desc (default desc)

10. **get_internal_logs** — Paginated internal-network SCA logs.
    - **protocol** : Protocol filter
    - **ip** : Source IP filter
    - **site_id** : Filter by site UUID
    - **page** : Page number (default 1)
    - **limit** : Page size (default 50, max 500)
    - **sort_by** : Sort column
    - **sort_order** : asc | desc

11. **get_ot_logs** — Paginated OT-network SCA logs (Modbus, DNP3, S7, …).
    - **protocol** : Protocol filter (modbus, dnp3, s7, …)
    - **ip** : Source IP filter
    - **site_id** : Filter by site UUID
    - **page** : Page number (default 1)
    - **limit** : Page size (default 50, max 500)
    - **sort_by** : Sort column
    - **sort_order** : asc | desc

12. **get_ad_logs** — Paginated Active-Directory (AD server) SCA logs.
    - **protocol** : Protocol filter
    - **ip** : Source IP filter
    - **site_id** : Filter by site UUID
    - **page** : Page number (default 1)
    - **limit** : Page size (default 50, max 500)
    - **sort_by** : Sort column
    - **sort_order** : asc | desc

13. **get_ai_threats_logs** — Paginated AI-threats (AI-deception layer) logs.
    - **protocol** : Protocol filter
    - **ip** : Source IP filter
    - **site_id** : Filter by site UUID
    - **page** : Page number (default 1)
    - **limit** : Page size (default 50, max 500)
    - **sort_by** : Sort column
    - **sort_order** : asc | desc

14. **get_attack_path** — Multi-stage attack trails for an IP address.
    - **ip** : Source IP address to trace (required)
    - **site_id** : Filter by site UUID
    - **limit** : Page size

15. **list_sites** — List sites the caller is authorised to see.

16. **get_site_summary** — Summary stats for a single site.
    - **site_id** : Site UUID (required)

17. **check_ip_reputation** — Check IP reputation via IPQS, AbuseIPDB or VirusTotal.
    - **ip** : IP address to check (required)
    - **source** : Reputation provider (ipqs | abuseipdb | virustotal, default ipqs)

18. **list_protocols** — List active protocols tracked by the platform.
    Returns ``{"protocols": [...]}``.

19. **get_alert_config** — Get the latest high-threat system alerts (threat_score >= 70).
    Returns ``{"alerts": [...], "count": N}``.

20. **list_audit_log** — List the immutable audit log (admin/auditor).
    - **limit** : Result limit (default 100, max 500)
    - **offset** : Skip this many rows
    - **actor** : Filter by actor email
    - **action** : Filter by action name (e.g. ticket.update)
    - **from_dt** : Entries at/after this time (ISO 8601)
    - **to_dt** : Entries at/before this time (ISO 8601)

21. **list_report_runs** — List report runs (scheduled CISO & board reports).
    - **schedule_id** : Filter by report schedule UUID
    - **limit** : Result limit (default 50, max 200)

22. **get_report_run** — Get details for a single report run.
    - **run_id** : Report run UUID (required)

