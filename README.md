# AMaze — Shuffle (SOAR) python-app

First-class **AMaze** deception-platform integration for **Shuffle** SOAR.
Query and operate AMaze tickets (actionable alerts), approvals, detection
logs (IT / OT / AD / AI), sites, IP reputation, audit and reporting from
within Shuffle workflows.

- **AMaze** (`mirrormire-amaze`) — MirrorMire AI's enterprise deception
  reporting platform (SCAs across IT, OT and AI surfaces).
- **Shuffle** — open-source SOAR that routes webhooks into visual automation
  workflows. This repo is the Shuffle **python-app** side of the integration.

## Repository layout

The Shuffle app lives in `amaze/1.0.0/` — the canonical `<app>/<version>/`
layout used by the upstream `Shuffle/python-apps` repository. The repo root
holds project-level docs (`README.md`, `PLAN.md`, `docs.md`) and the
upstream-ready app folder.

| Path | Purpose |
| --- | --- |
| `amaze/1.0.0/src/app.py` | Shuffle SDK entry point — `class AMaze(AppBase)`, one method per action |
| `amaze/1.0.0/src/amaze_client.py` | Thin REST client for the AMaze API v3 |
| `amaze/1.0.0/api.yaml` | Shuffle app definition — `authentication:` + all actions |
| `amaze/1.0.0/requirements.txt` | Runtime deps (`requests`) — the SDK comes from the base image |
| `amaze/1.0.0/requirements-dev.txt` | Local dev/test deps (SDK, pytest, PyYAML) |
| `amaze/1.0.0/Dockerfile` | Builds on `frikky/shuffle:app_sdk` |
| `amaze/1.0.0/tests/` | Pytest: client behaviour + `api.yaml` ↔ method parity |
| `docs.md` | Extended integration docs and Shuffle workflow recipes |
| `PLAN.md` | Two-sided implementation plan (AMaze platform ↔ Shuffle app) |

To contribute upstream, open a PR against `Shuffle/python-apps` adding the
`amaze/1.0.0/` folder (see its own `README.md` for app-specific details).

## Authentication

Configure once in Shuffle (the `authentication:` block in `api.yaml`):

- `base_url` — AMaze API base URL, e.g. `https://amaze.example.com`
- `bearer_token` — JWT / API token for the AMaze REST API

Recommended AMaze account for a Shuffle service token: role **analyst**
(scoped to the tenant and sites Shuffle is allowed to operate), or **admin**
if workflows must test integrations or retry dispatches.

## Local testing (no Shuffle instance needed)

```bash
cd amaze/1.0.0
pip install -r requirements.txt -r requirements-dev.txt

# With the Shuffle SDK installed:
python src/app.py --standalone --action=list_tickets \
    base_url=http://localhost:8000 bearer_token=TOKEN status=OPEN limit=5

# Or with the built-in plain CLI (no SDK):
python src/app.py list_tickets --base-url http://localhost:8000 \
    --bearer-token TOKEN --status OPEN --limit 5
```

## Build & run (container-first)

```bash
cd amaze/1.0.0
docker build -t shuffle-amaze:1.0.0 .
docker run --rm shuffle-amaze:1.0.0
```

## Tests

```bash
cd amaze/1.0.0
pip install -r requirements-dev.txt pytest
pytest -q
```

The parity test fails if any `api.yaml` action has no matching method in
`src/app.py` (or vice versa), keeping the app definition and code in sync.

## Example Shuffle workflow

```
Webhook (AMaze Rich Alert)
  → IF body.threat_score >= 95
      → AMaze.get_ticket(ticket_id=body.ticket_id)
      → Slack: "Critical {{body.protocol}} attack from {{body.src_ip}}"
      → AMaze.update_ticket(status=IN_PROGRESS)
      → [block src_ip at the firewall]
      → AMaze.update_ticket(status=CLOSED, description="Auto-remediated")
  → ELSE
      → AMaze.update_ticket(status=IN_PROGRESS)
      → AMaze.list_approvals(status=pending)  # surface HITL queue
```

See `docs.md` for the full recipes and the AMaze `docs/integrations/shuffle.md`
recipe for configuring the webhook trigger on the AMaze side.
