"""Tests for CORS and subnet restriction middleware."""

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
