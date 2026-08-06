# AMaze Shuffle app — integration documentation

This doc details the two directions of the AMaze ↔ Shuffle integration and the
Shuffle workflow recipes that use the `amaze` python-app in this repo.

## Direction 1 — AMaze → Shuffle (webhook trigger)

AMaze's outbound dispatcher (`amaze-ingest`) POSTs a **Rich Alert** JSON
payload to every matching integration (webhook / Slack / Teams / generic).
Configure a Shuffle **Webhook** trigger as the integration endpoint:

1. In Shuffle, create a workflow and drag in the **Webhook** trigger.
2. Copy the generated hook URL, e.g. `https://shuffler.io/api/hooks/webhook_<uuid>`.
3. Set the trigger auth header, e.g. `Authorization: Bearer <token>`.
4. In AMaze, **Settings → Integrations → New integration**:
   - Name: `shuffle-production`
   - Type: `webhook`
   - Endpoint URL: the Shuffle hook URL
   - Auth mode: `bearer`, Secret: the same `<token>`
   - Min threat score: `90` (or lower for more noise)

### Rich Alert payload (stable contract)

```json
{
  "alert_type": "neural_event.actionable",
  "schema_version": 1,
  "timestamp": "2026-08-05T10:00:00Z",
  "protocol": "ssh",
  "src_ip": "185.220.101.34",
  "dest_ip": "10.0.0.7",
  "threat_score": 97,
  "fraud_score": 90,
  "threat_type": "brute_force",
  "country": "DE",
  "lat": 52.52,
  "lon": 13.4,
  "username": "root",
  "user_agent": "...",
  "ja3_hash": "...",
  "initial_ttp": ["T1110"],
  "ttp": "T1110.001",
  "site_id": "...",
  "sca_id": "...",
  "sca_name": "ssh-01",
  "vm_id": "VM-NZ-Node-A",
  "enrichment_details": {"ipqs": {"fraud_score": 88, "is_proxy": true}},
  "logline": "..."
}
```

> **Known gap (Side A plan):** the payload currently does **not** include
> `ticket_id` / `neural_event_id`. The recommended AMaze change is to add both
> to `_RICH_ALERT_FIELDS` so a webhook workflow can close the loop directly.
> Until then, correlate by `src_ip` (e.g. `AMaze.list_tickets(ip=...)`) or use
> `AMaze.get_ticket` after resolving via `AMaze.list_external_logs`.

Shuffle reads the body directly: `{{body.threat_score}}`, `{{body.src_ip}}`,
`{{body.enrichment_details.ipqs.fraud_score}}`, etc.

## Direction 2 — Shuffle → AMaze (this app)

The `amaze` app gives Shuffle full read/operate access. Action groups:

| Group | Actions |
| --- | --- |
| Tickets | `list_tickets`, `get_ticket`, `update_ticket`, `delete_ticket`, `list_ticket_dispatches`, `retry_ticket_dispatch` |
| Integrations | `test_integration` |
| Approvals | `list_approvals` |
| Logs | `get_external_logs`, `get_internal_logs`, `get_ot_logs`, `get_ad_logs`, `get_ai_threats_logs`, `get_attack_path` |
| Context | `list_sites`, `get_site_summary`, `check_ip_reputation`, `list_protocols`, `get_alert_config` |
| Audit/Reports | `list_audit_log`, `list_report_runs`, `get_report_run` |

All actions take `base_url` + `bearer_token` automatically (from the
`authentication:` block) plus their specific parameters.

### RBAC notes (which AMaze roles can call what)

- Reads (tickets, logs, sites, approvals) — admin / analyst / auditor.
- `test_integration`, `retry_ticket_dispatch`, `delete_ticket`,
  `list_audit_log` — admin.
- `update_ticket` — admin / analyst.

## Workflow recipes

### 1. Automated triage + remediation (critical)

```
Webhook (AMaze Rich Alert)
  → IF body.threat_score >= 95
      → AMaze.get_ticket(ticket_id=body.ticket_id)
      → Slack: "Critical {{body.protocol}} from {{body.src_ip}} ({{body.ttp}})"
      → AMaze.update_ticket(ticket_id=body.ticket_id, status=IN_PROGRESS)
      → Firewall: block {{body.src_ip}}
      → AMaze.update_ticket(ticket_id=body.ticket_id, status=CLOSED,
                            description="Auto-remediated by Shuffle")
  → ELSE
      → AMaze.update_ticket(ticket_id=body.ticket_id, status=IN_PROGRESS)
```

### 2. Approval (HITL) queue surfacing

```
Schedule (every 15 min)
  → AMaze.list_approvals(status=pending)
  → Slack: "N pending AMaze dispatch approvals" (review in the AMaze UI)
```

### 3. On-demand enrichment / investigation

```
AMaze.list_external_logs(ip=185.220.101.34, limit=50)
  → AMaze.check_ip_reputation(ip=185.220.101.34, source=ipqs)
  → AMaze.get_attack_path()
  → AMaze.update_ticket(ticket_id=...,
                        description="Investigation: 185.220.101.34")
```

### 4. Reporting digest

```
AMaze.list_report_runs(limit=10)
  → AMaze.get_report_run(run_id=...)
  → Slack: weekly AMaze report digest to the CISO channel
```

## Close the loop (direct API, no app needed)

Any workflow can update an AMaze ticket directly:

```
POST {{AMAZE_URL}}/api/v3/tickets/{{ticket_id}}
Authorization: Bearer {{AMAZE_ADMIN_JWT}}
{ "status": "CLOSED", "description": "Auto-remediated by Shuffle" }
```

This mirrors `docs/integrations/shuffle.md` in `mirrormire-amaze` and what
`services/shuffle-phantom` does in the demo topology.
