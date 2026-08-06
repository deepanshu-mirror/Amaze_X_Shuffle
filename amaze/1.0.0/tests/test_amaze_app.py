"""Tests for the AMaze Shuffle python-app.

Covers:
  * the REST client's URL/header/param/body/TLS-verify/error behaviour,
  * api.yaml <-> src/app.py parity (action names + parameter names),
  * the local CLI runner's argument wiring (incl. --action-filter),
  * the Shuffle SDK standalone dispatch path.

Run with:  pytest -q   (from the app version directory)
"""

from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

import pytest

from amaze_client import AmazeClient, AmazeAPIError
from app import AMaze

ROOT = Path(__file__).resolve().parents[1]


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", content=b"{}"):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.content = content
        self.reason = "REASON"

    def json(self):
        return self._json


def _install_fake_request(monkeypatch, fake_request):
    import requests

    monkeypatch.setattr(requests, "request", fake_request)


def _capture_request(monkeypatch, status_code=200, json_data=None):
    captured = {}

    def fake_request(
        method, url, headers=None, params=None, json=None, timeout=None, verify=None
    ):
        captured.update(
            method=method, url=url, headers=headers,
            params=params, json=json, timeout=timeout, verify=verify,
        )
        return FakeResponse(status_code, json_data, "", "{}")

    _install_fake_request(monkeypatch, fake_request)
    return captured


# ── Client behaviour ─────────────────────────────────────────────────────────


def test_client_builds_request(monkeypatch):
    captured = _capture_request(monkeypatch, json_data=[{"id": "abc"}])
    client = AmazeClient("https://amaze.example.com/", "tok123")
    result = client.list_tickets(status="OPEN", ip="185.220.101.34", limit=5)

    assert captured["method"] == "GET"
    assert captured["url"] == "https://amaze.example.com/api/v3/tickets/"
    assert captured["headers"]["Authorization"] == "Bearer tok123"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["params"] == {
        "status": "OPEN",
        "ip": "185.220.101.34",
        "limit": 5,
    }
    assert result == [{"id": "abc"}]


def test_client_drops_none_and_empty_params(monkeypatch):
    captured = _capture_request(monkeypatch, json_data=[])
    client = AmazeClient("https://amaze.example.com", "tok")
    client.list_tickets(status="OPEN")

    assert captured["params"] == {"status": "OPEN"}


def test_client_http_error_raises(monkeypatch):
    def fake_request(
        method, url, headers=None, params=None, json=None, timeout=None, verify=None
    ):
        return FakeResponse(401, None, "Unauthorized", b"{}")

    _install_fake_request(monkeypatch, fake_request)
    client = AmazeClient("https://amaze.example.com", "tok")
    with pytest.raises(AmazeAPIError, match="401") as excinfo:
        client.get_ticket("00000000-0000-0000-0000-000000000000")
    # AmazeAPIError is a RuntimeError subclass and carries the status code.
    assert isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.status_code == 401


def test_client_update_ticket_requires_field(monkeypatch):
    client = AmazeClient("https://amaze.example.com", "tok")
    with pytest.raises(ValueError, match="At least one"):
        client.update_ticket("t1")


def test_client_204_returns_none(monkeypatch):
    captured = _capture_request(monkeypatch, status_code=204)
    client = AmazeClient("https://amaze.example.com", "tok")
    assert client.delete_ticket("t1") is None
    assert captured["method"] == "DELETE"


def test_client_check_ip_reputation(monkeypatch):
    captured = _capture_request(monkeypatch, json_data={"ip": "1.2.3.4"})
    client = AmazeClient("https://amaze.example.com", "tok")
    client.check_ip_reputation("1.2.3.4", source="ipqs")

    assert captured["url"] == "https://amaze.example.com/api/reputation/ipqs"
    assert captured["json"] == {"ip": "1.2.3.4"}


def test_client_verify_defaults_true(monkeypatch):
    captured = _capture_request(monkeypatch, json_data={})
    AmazeClient("https://amaze.example.com", "tok").list_tickets()
    assert captured["verify"] is True


def test_client_verify_parses_shuffle_strings(monkeypatch):
    captured = _capture_request(monkeypatch, json_data={})
    AmazeClient("https://amaze.example.com", "tok", verify="false").list_tickets()
    assert captured["verify"] is False

    captured = _capture_request(monkeypatch, json_data={})
    AmazeClient("https://amaze.example.com", "tok", verify="true").list_tickets()
    assert captured["verify"] is True

    captured = _capture_request(monkeypatch, json_data={})
    AmazeClient("https://amaze.example.com", "tok", verify=False).list_tickets()
    assert captured["verify"] is False


def test_client_verify_flows_from_app_action(monkeypatch):
    # ``verify`` is declared under ``authentication:`` and injected by Shuffle
    # into every action, so an action must forward it to the client.
    captured = _capture_request(monkeypatch, json_data=[])
    AMaze().list_tickets(
        "https://amaze.example.com", "tok", verify="false", status="OPEN"
    )
    assert captured["verify"] is False


def test_client_verify_flows_through_log_action(monkeypatch):
    captured = _capture_request(monkeypatch, json_data={})
    AMaze().get_external_logs(
        "https://amaze.example.com", "tok", verify="false", protocol="ssh"
    )
    assert captured["verify"] is False
    assert captured["params"] == {"protocol": "ssh"}


# ── api.yaml <-> app.py parity ───────────────────────────────────────────────


def _load_spec():
    yaml = pytest.importorskip("yaml")
    with open(ROOT / "api.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _app_action_names():
    return {
        name
        for name, value in AMaze.__dict__.items()
        if callable(value) and not name.startswith("_")
    }


def test_api_yaml_is_valid_and_has_auth():
    spec = _load_spec()
    assert spec["name"] == AMaze.app_name, "api.yaml name must match app_name"
    assert "walkoff_version" in spec
    assert spec["authentication"]["required"] is True
    auth_names = {p["name"] for p in spec["authentication"]["parameters"]}
    assert {"base_url", "bearer_token"} <= auth_names


def test_api_yaml_actions_match_app_methods():
    spec = _load_spec()
    yaml_actions = {action["name"] for action in spec["actions"]}
    assert yaml_actions == _app_action_names()


def test_action_parameters_match_method_signatures():
    spec = _load_spec()
    auth_names = {p["name"] for p in spec["authentication"]["parameters"]}
    for action in spec["actions"]:
        method = getattr(AMaze, action["name"])
        sig_params = set(inspect.signature(method).parameters) - ({"self"} | auth_names)
        yaml_params = {p["name"] for p in action.get("parameters", [])}
        assert sig_params == yaml_params, f"parameter mismatch on {action['name']}"


# ── Local CLI runner wiring ──────────────────────────────────────────────────


def _patch_client(monkeypatch, method_name, captured, client_kwargs=None):
    """Point the app at a fake client that records the action's kwargs.

    ``captured`` collects the client method's kwargs; ``client_kwargs`` (if
    given) collects the kwargs passed to the client constructor (base_url,
    bearer_token, verify).
    """

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def handler(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

    setattr(FakeClient, method_name, FakeClient.handler)

    def _fake_client(base_url, bearer_token, verify=None):
        if client_kwargs is not None:
            client_kwargs.update(
                base_url=base_url, bearer_token=bearer_token, verify=verify
            )
        return FakeClient()

    monkeypatch.setattr(AMaze, "_client", staticmethod(_fake_client))


def test_cli_maps_args_to_action(monkeypatch, capsys):
    captured = {}
    client_kwargs = {}
    _patch_client(monkeypatch, "list_tickets", captured, client_kwargs)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py", "list_tickets", "--base-url", "http://x",
            "--bearer-token", "T", "--status", "OPEN", "--limit", "5",
            "--verify", "false",
        ],
    )
    AMaze._run_cli()
    assert captured["status"] == "OPEN"
    assert captured["limit"] == 5
    # --verify flows through the action into the client constructor.
    assert client_kwargs["verify"] == "false"
    assert "ok" in capsys.readouterr().out


def test_cli_action_filter_maps_to_action(monkeypatch):
    """Regression: --action-filter must reach list_audit_log's ``action`` kwarg."""
    captured = {}
    _patch_client(monkeypatch, "list_audit_log", captured)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py", "list_audit_log", "--base-url", "http://x",
            "--bearer-token", "T", "--action-filter", "ticket.update",
        ],
    )
    AMaze._run_cli()
    assert captured.get("action") == "ticket.update"


def test_cli_unknown_action_exits(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["app.py", "nope", "--base-url", "http://x", "--bearer-token", "T"]
    )
    with pytest.raises(SystemExit):
        AMaze._run_cli()


# ── Shuffle SDK standalone dispatch ──────────────────────────────────────────


def test_sdk_standalone_dispatch(monkeypatch, capsys):
    """Exercise the real SDK execute_action() path via --standalone (skipped
    when the SDK is not installed locally)."""
    pytest.importorskip("shuffle_sdk")
    captured = {}
    _patch_client(monkeypatch, "list_tickets", captured)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py", "--standalone", "--action=list_tickets",
            "base_url=http://x", "bearer_token=T", "status=OPEN", "limit=5",
        ],
    )
    # The SDK exits() after a successful standalone run.
    with pytest.raises(SystemExit):
        AMaze.run()
    assert captured.get("status") == "OPEN"
    assert "ok" in capsys.readouterr().out
