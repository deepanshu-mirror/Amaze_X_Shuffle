"""Tests for the AMaze Shuffle python-app.

Covers:
  * the REST client's URL/header/param/body/error behaviour,
  * api.yaml <-> src/app.py parity (action names + parameter names).

Run with:  pytest -q   (from the repository root)
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest

from amaze_client import AmazeClient
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

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        captured.update(
            method=method, url=url, headers=headers,
            params=params, json=json, timeout=timeout,
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
    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        return FakeResponse(401, None, "Unauthorized", b"{}")

    _install_fake_request(monkeypatch, fake_request)
    client = AmazeClient("https://amaze.example.com", "tok")
    with pytest.raises(RuntimeError, match="401"):
        client.get_ticket("00000000-0000-0000-0000-000000000000")


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
    for action in spec["actions"]:
        method = getattr(AMaze, action["name"])
        sig_params = set(inspect.signature(method).parameters) - {"self", "base_url", "bearer_token"}
        yaml_params = {p["name"] for p in action.get("parameters", [])}
        assert sig_params == yaml_params, f"parameter mismatch on {action['name']}"
