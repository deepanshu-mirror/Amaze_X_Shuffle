# AMaze — Shuffle (SOAR) python-app

First-class **AMaze** deception-platform integration for **Shuffle** SOAR.
Query and operate AMaze tickets (actionable alerts), approvals, detection
logs (IT / OT / AD / AI), sites, IP reputation, audit and reporting from
within Shuffle workflows.

- **AMaze** (`mirrormire-amaze`) — MirrorMire AI's enterprise deception
  reporting platform (SCAs across IT, OT and AI surfaces).
- **Shuffle** — open-source SOAR that routes webhooks into visual automation
  workflows. This is the Shuffle **python-app** side of the integration.

> Upstream layout: this folder is a single app *version*. In the
> `Shuffle/python-apps` repository it is the `amaze/1.0.0/` app.

## Files

| Path | Purpose |
| --- | --- |
| `src/app.py` | Shuffle SDK entry point — `class AMaze(AppBase)`, one method per action |
| `src/amaze_client.py` | Thin REST client for the AMaze API v3 |
| `api.yaml` | Shuffle app definition — `authentication:` + all actions |
| `requirements.txt` | Runtime deps (`requests`) — the SDK comes from the base image |
| `requirements-dev.txt` | Local dev/test deps (SDK, pytest, PyYAML) |
| `Dockerfile` | Builds on `frikky/shuffle:app_sdk` |
| `tests/` | Pytest: client behaviour + `api.yaml` ↔ method parity |

## Authentication

Configure once in Shuffle (the `authentication:` block in `api.yaml`):

- `base_url` — AMaze API base URL, e.g. `https://amaze.example.com`
- `bearer_token` — JWT / API token for the AMaze REST API

Recommended AMaze account for a Shuffle service token: role **analyst**
(scoped to the tenant and sites Shuffle is allowed to operate), or **admin**
if workflows must test integrations or retry dispatches.

## Local testing (no Shuffle instance needed)

```bash
pip install -r requirements.txt -r requirements-dev.txt

# With the Shuffle SDK installed (standalone):
python src/app.py --standalone --action=list_tickets \
    base_url=http://localhost:8000 bearer_token=TOKEN status=OPEN limit=5

# Or with the built-in plain CLI (no SDK):
python src/app.py list_tickets --base-url http://localhost:8000 \
    --bearer-token TOKEN --status OPEN --limit 5
```

## Build & run (container-first)

```bash
docker build -t shuffle-amaze:1.0.0 .
docker run --rm shuffle-amaze:1.0.0
```

## Tests

```bash
pip install -r requirements-dev.txt pytest
pytest -q
```

The parity test fails if any `api.yaml` action has no matching method in
`src/app.py` (or vice versa), keeping the app definition and code in sync.

## Actions

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
