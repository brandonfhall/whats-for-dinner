"""Tests for CORS, subnet restriction, and access-log middleware."""

import logging
from unittest.mock import patch


def test_cors_wildcard_allows_any_origin(client):
    """CORS middleware includes wildcard allow-origin header for any Origin."""
    r = client.get("/api/ai/status", headers={"Origin": "https://example.com"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "*"


def test_subnet_allows_all_when_unset(client):
    """When ALLOWED_SUBNETS is not set, all IPs are allowed through."""
    # No patch needed — ALLOWED_SUBNETS is absent in the test environment
    r = client.get("/api/ai/status", headers={"X-Real-IP": "1.2.3.4"})
    assert r.status_code == 200


def test_subnet_allows_ip_in_network(client):
    """An IP within the configured CIDR is allowed."""
    with patch.dict("os.environ", {"ALLOWED_SUBNETS": "192.168.1.0/24"}):
        r = client.get("/api/ai/status", headers={"X-Real-IP": "192.168.1.42"})
    assert r.status_code == 200


def test_subnet_blocks_disallowed_ip(client):
    """An IP outside the configured CIDR receives a 403."""
    with patch.dict("os.environ", {"ALLOWED_SUBNETS": "192.168.1.0/24"}):
        r = client.get("/api/ai/status", headers={"X-Real-IP": "10.0.0.1"})
    assert r.status_code == 403


def test_subnet_fallback_to_x_forwarded_for(client):
    """Without X-Real-IP, the first IP in X-Forwarded-For is used."""
    with patch.dict("os.environ", {"ALLOWED_SUBNETS": "10.0.0.0/8"}):
        r = client.get(
            "/api/ai/status",
            headers={"X-Forwarded-For": "10.5.5.5, 1.2.3.4"},
        )
    assert r.status_code == 200


# ── AccessLogMiddleware ───────────────────────────────────────────────────────

def test_access_log_records_successful_request(client):
    """AccessLogMiddleware calls log() at INFO level for successful API requests."""
    with patch("app.main._access_log") as mock_log:
        r = client.get("/api/settings")
    assert r.status_code == 200
    mock_log.log.assert_called_once()
    level, fmt, _ip, method, path, status, _ms = mock_log.log.call_args[0]
    assert level == logging.INFO
    assert method == "GET"
    assert path == "/api/settings"
    assert status == 200


def test_access_log_warns_on_4xx(client):
    """AccessLogMiddleware logs at WARNING level when the response is 4xx."""
    with patch("app.main._access_log") as mock_log:
        with patch.dict("os.environ", {"ALLOWED_SUBNETS": "192.168.1.0/24"}):
            r = client.get("/api/settings", headers={"X-Real-IP": "10.0.0.1"})
    assert r.status_code == 403
    mock_log.log.assert_called_once()
    level, _fmt, _ip, _method, _path, status, _ms = mock_log.log.call_args[0]
    assert level == logging.WARNING
    assert status == 403


def test_access_log_skips_static_paths(client):
    """AccessLogMiddleware does not log requests to /static/."""
    with patch("app.main._access_log") as mock_log:
        client.get("/static/app.js")
    mock_log.log.assert_not_called()


# ── SecurityHeadersMiddleware ─────────────────────────────────────────────────

def test_security_headers_present(client):
    """SecurityHeadersMiddleware adds all expected headers to API responses."""
    r = client.get("/api/settings")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "SAMEORIGIN"
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    csp = r.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "script-src 'self' 'unsafe-eval'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp


def test_security_headers_on_static(client):
    """SecurityHeadersMiddleware also sets headers on static file responses."""
    r = client.get("/static/app.js")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "SAMEORIGIN"


def test_static_assets_cache_control_no_cache(client):
    """Static files must include Cache-Control: no-cache so deploys take effect immediately."""
    r = client.get("/static/app.js")
    assert r.headers.get("cache-control") == "no-cache"


def test_api_responses_no_cache_control(client):
    """API responses should not have the static-asset Cache-Control header."""
    r = client.get("/api/settings")
    assert r.headers.get("cache-control") != "no-cache"
