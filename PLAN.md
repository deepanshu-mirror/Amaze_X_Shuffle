# AMaze ↔ Shuffle (SOAR) — Evaluation & Two-Sided Implementation Plan

This document is the working plan for turning **mirrormire-amaze** (a deception
reporting platform) into a first-class citizen of **Shuffle** (an open-source
SOAR). It covers:

1. [Platform evaluation — what AMaze already is](#1-platform-evaluation)
2. [SOAR-relevant capability map](#2-soar-relevant-capability-map)
3. [Review of the current `Amaze_X_Shuffle` app](#3-review-of-the-current-app)
4. [Plan side A — AMaze platform changes](#4-plan-side-a--amaze-platform-changes)
5. [Plan side B — Shuffle python-app changes](#5-plan-side-b--shuffle-python-app-changes)
6. [Reference workflows](#6-reference-workflows)
7. [Rollout / acceptance checklist](#7-rollout--acceptance-checklist)

---

## 1. Platform evaluation

`mirrormire-amaze` is the **AMaze (AIMaze)** enterprise deception platform —
MirrorMire AI's "Proactive CyberResilience as a Service". In short:

- **Deception surfaces:** IT, OT, and AI. Synthetic Cognitive Agents (SCAs)
  impersonate real assets across ~20 protocols (SSH, FTP, RDP, HTTP, MySQL,
  Redis, XAMPP, IoT, Windows DC/WS, Modbus, ENIP, DNP3, BACnet, S7, OPC-UA,
  IEC-104, MQTT, plus AI-agent honeypots via `aisca/` and `otsca/`).
- **Detection pipeline:** SCA events → NATS JetStream → `amaze-ingest`
  (decrypt, IP-reputation, GeoIP, ML inference) → `neural_events` →
  **tickets ("actionable alerts")** when `threat_score >= 90`.
- **Reporting/ops core (`amaze-core`, FastAPI :8000):** REST API v3 with JWT +
  RBAC (admin / analyst / auditor / mssp_admin), multi-tenant + site scoping,
  tickets, approvals, outbound integrations, audit log, reports, deployment
  planner, topology, executive summaries, an AI analyst (`/api/v3/chat`).
- **Outbound dispatch (the SOAR hook):** `amaze-ingest` fans out a **Rich
  Alert** JSON payload to configured integrations (webhook / Slack / Teams /
  generic, auth modes `none` / `bearer` / `api-key` / `hmac-sha256`, optional
  JWT rotation, syslog variant). Approvals gate HITL decisions.

**Verdict:** AMaze is *not* a SOAR and should not try to be one — but it has
everything a SOAR needs from a **detection + reporting source**:

- high-signal detections (tickets with MITRE TTPs, threat/fraud scores, dedup,
  remediation text),
- enrichment (IP reputation, GeoIP, JA3, enrichment_details),
- an audit-grade approval/dispatch ledger,
- postural/reporting data (topology, executive summary, reports).

The right integration shape is **bidirectional**:

- **AMaze → Shuffle (detect/dispatch):** webhook trigger carrying the Rich
  Alert; Shuffle runs response playbooks.
- **Shuffle → AMaze (operate/respond):** a python-app that queries tickets,
  logs, sites; updates tickets; retries dispatches; closes the loop by
  flipping ticket status.

---

## 2. SOAR-relevant capability map

Verified against `services/amaze-core/app/routers/` (all under REST API v3):

| Area | Endpoints | SOAR use |
| --- | --- | --- |
| Tickets | `GET /api/v3/tickets/`, `GET/PUT/DELETE /api/v3/tickets/{id}` | Enrich, triage, update, close, re-dispatch |
| Dispatch history | `GET .../dispatches`, `POST .../retry` | Verify delivery, retry failures |
| Approvals | `GET /api/v3/approvals/` | HITL gate: surface pending decisions |
| Integrations | `POST .../{id}/test` | Health-check the dispatch path |
| Logs / detection data | `GET /api/v3/{external,internal,ot,active-directory,ai-threats,dionamaze}/logs`, `GET /api/v3/attack-path` | Correlate + pivot during investigation |
| Sites | `GET /api/v3/sites/`, `.../{id}/summary` | Fleet/MSP scoping |
| Enrichment | `POST /api/reputation/{ipqs,abuseipdb,virustotal}` | IP reputation lookups (JWT-gated) |
| Audit | `GET /api/v3/audit-log/`, `/export` | Immutable evidence for case files |
| Reports | `GET /api/v3/reports/runs`, `.../{id}`, `POST .../generate` | Scheduled/signed reporting |
| System | `GET /api/v3/system/{protocols,alert}` | Context (enabled protocols, alert config) |

> RBAC note for workflow authors: `test_integration` is **admin+auditor**;
> most reads are admin+analyst+auditor. A Shuffle service token should be an
> **analyst** or **admin** scoped to the relevant tenant/sites.

---

## 3. Review of the current app

The existing `Amaze_X_Shuffle` scaffold has the right idea (ticket + approval +
integration actions) and the **API paths are correct** (they match the real
routers). What needs fixing to be a real Shuffle python-app:

| # | Issue | Current | Required |
| --- | --- | --- | --- |
| 1 | **SDK base import** | `from app_base import AppBase` (try/except → `object`) | `from walkoff_app_sdk.app_base import AppBase` (try/except chain so it also runs locally) |
| 2 | **Dockerfile** | `FROM python:3.11-slim`, `CMD ["python","app.py"]` | `FROM frikky/shuffle:app_sdk`, multi-stage pip install, `COPY src /app`, `CMD python app.py --log-level DEBUG` |
| 3 | **requirements.txt** | only `requests` | add `shuffle_sdk` (for local/SDK runs) |
| 4 | **api.yaml format** | missing `walkoff_version`, auth repeated per action | add `walkoff_version`, centralize `authentication:` block, drop per-action auth params |
| 5 | **Action coverage** | 9 actions (tickets/approvals/integrations only) | expand to logs, sites, reputation, audit, reports, dispatch history |
| 6 | **Entry point** | root `app.py` wrapper | canonical `src/app.py` with `if __name__ == "__main__": App.run()` (root wrapper removed) |
| 7 | **Tests** | none | pytest: client URL/body/headers, api.yaml ↔ method parity, arg parsing |
| 8 | **Versioning/contribution layout** | flat repo | document drop-in layout `amaze/1.0.0/` for upstream contribution to `Shuffle/python-apps` |

Also fixed/added: `from`/`to` time filters on tickets, `remediation` on update,
dispatch list/retry, reputation proxy, audit/report reads — all verified
against the routers.

---

## 4. Plan side A — AMaze platform changes

These are *recommended* platform-side changes (in `mirrormire-amaze`) to make
the Shuffle integration production-grade. None block the app in this repo.

1. **Add `ticket_id` / `neural_event_id` to the outbound Rich Alert payload.**
   Today `_RICH_ALERT_FIELDS` (both `amaze-ingest/app/pipeline/dispatcher.py`
   and `amaze-core/app/services/integration_svc.py`) omits them, so the
   existing `docs/integrations/shuffle.md` recipe's `{{body.ticket_id}}` is
   empty. Adding these two fields (when known) lets a Shuffle webhook workflow
   close the loop without a lookup.
2. **Ship a first-class "Shuffle" integration template/type.** Right now
   Shuffle is configured as a generic `webhook`. A dedicated recipe (name,
   recommended auth = `bearer`, suggested `min_threat_score`) in the UI and in
   `docs/integrations/shuffle.md` reduces setup error. (No code change
   strictly required — `generic`/`webhook` already covers it.)
3. **Optional: a dedicated outbound webhook schema marker.** Keep
   `alert_type: "neural_event.actionable"` + `schema_version: 1` (already
   present) and document the frozen payload in
   `docs/integrations/shuffle.md` so workflow authors can rely on it.
4. **Optional: inbound "SOAR callback" endpoint.** A thin endpoint (e.g.
   `POST /api/v3/soar/events`) that records a SOAR action outcome against a
   ticket/dispatch would give AMaze a first-class "handled by Shuffle" trail.
   Today the loopback works via the normal ticket update API (as
   `shuffle-phantom` demonstrates), so this is nice-to-have.
5. **Service-token guidance.** Document the recommended AMaze account for
   Shuffle (role `analyst`, tenant-scoped, site-scoped) and where to mint it,
   so RBAC keeps working when Shuffle calls the API.
6. **Regression guard:** a test asserting the Rich Alert payload contract
   (fields + `schema_version`) stays stable — since it is now a public SOAR
   contract.

## 5. Plan side B — Shuffle python-app changes

Implemented in this repo (`Amaze_X_Shuffle`):

1. Restructure to Shuffle conventions (see §3 table); the app lives in
   `amaze/1.0.0/` — the canonical `<app>/<version>/` layout used by upstream
   `Shuffle/python-apps` — with project-level docs kept at the repo root.
2. `amaze/1.0.0/src/app.py` — `class AMaze(AppBase)`, `app_name = "amaze"`
   (matches `api.yaml` `name`), one method per action, auth args `base_url` +
   `bearer_token` injected from the `authentication:` block.
3. `amaze/1.0.0/src/amaze_client.py` — thin REST client (JSON, bearer auth,
   timeouts, sensible errors).
4. `amaze/1.0.0/api.yaml` — full OpenAPI-ish definition with `walkoff_version`,
   `authentication:`, and ~22 actions grouped by capability.
5. `amaze/1.0.0/Dockerfile` — `frikky/shuffle:app_sdk` base (Alpine, app_sdk),
   installs `requests`, `CMD python app.py --log-level DEBUG`. The SDK is
   bundled in the base image; `requirements-dev.txt` carries it for local runs.
6. `amaze/1.0.0/tests/` — parity + client behavior tests.
7. `README.md` (repo + app) — usage, auth, and end-to-end workflow recipes
   (webhook ingest + response + loopback), aligned with the existing
   `docs/integrations/shuffle.md` in `mirrormire-amaze`.

**Contribution path:** the app already sits at `amaze/1.0.0/`; fork
`Shuffle/python-apps`, copy `amaze/1.0.0/` into the fork, open a PR. (App name
`amaze`; category `Case Management` + `SIEM`; license MIT.)

---

## 6. Reference workflows

```
Webhook (AMaze Rich Alert) →
  IF body.threat_score >= 95 →
    AMaze.get_ticket(body.ticket_id)            # pull remediation + enrichment
    Slack notify SOC + AMaze.update_ticket(IN_PROGRESS)
    Cilium/firewall isolate body.src_ip
    AMaze.update_ticket(CLOSED, "Auto-remediated")
  ELSE → AMaze.update_ticket(IN_PROGRESS) → AMaze.list_tickets() → analyst review
```

```
Schedule (every 15 min) →
  AMaze.list_approvals(status="pending") → notify SOC (review in AMaze UI)
```

```
On-demand →
  AMaze.get_external_logs(src_ip=...) → AMaze.check_ip_reputation(ip) →
  AMaze.get_attack_path() → AMaze.update_ticket(...)
```

---

## 7. Rollout / acceptance checklist

- [ ] `cd amaze/1.0.0 && pip install -r requirements.txt -r requirements-dev.txt` + `python src/app.py --standalone --action=list_tickets base_url=... bearer_token=...` returns tickets.
- [ ] `cd amaze/1.0.0 && pytest` (parity + client tests) green.
- [ ] Docker build from `frikky/shuffle:app_sdk` succeeds (`cd amaze/1.0.0 && docker build .`).
- [ ] Uploaded/hotloaded into a Shuffle instance; `authentication` fields map to `base_url`/`bearer_token`.
- [ ] AMaze → Shuffle webhook trigger receives a Rich Alert; workflow parses `body.threat_score`, `body.src_ip`.
- [ ] Loopback: workflow updates the ticket to `CLOSED` and it reflects in the AMaze UI.
- [ ] (Side A) `ticket_id` present in Rich Alert payload; `docs/integrations/shuffle.md` updated.
