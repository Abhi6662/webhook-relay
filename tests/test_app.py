"""Tests for webhook relay app."""

import hashlib
import hmac
import importlib
import os
import sys
from fastapi.testclient import TestClient


def _get_client_with_secret(secret: str = "", strict: str = "false"):
    """Get a test client with specific secret configuration."""
    os.environ["WEBHOOK_SECRET"] = secret
    os.environ["WEBHOOK_STRICT_MODE"] = strict
    
    # Reload the app module to pick up new env vars
    if "webhook_relay.app" in sys.modules:
        importlib.reload(sys.modules["webhook_relay.app"])
    if "webhook_relay" in sys.modules:
        importlib.reload(sys.modules["webhook_relay"])
    
    from webhook_relay import app
    return TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    client = _get_client_with_secret("test-secret")
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "queue" in data


def test_receive_webhook_without_secret():
    """Test webhook reception works when no secret is configured."""
    client = _get_client_with_secret("")  # No secret
    response = client.post(
        "/webhook",
        json={"test": "data"},
        headers={"X-Event-Type": "test.event"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "id" in data


def test_receive_webhook_with_valid_signature():
    """Test webhook reception with valid HMAC signature."""
    client = _get_client_with_secret("test-secret")
    payload = b'{"test": "data"}'
    signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Signature": signature,
            "X-Event-Type": "signed.event",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


def test_receive_webhook_with_invalid_signature():
    """Test webhook rejection with invalid HMAC signature."""
    client = _get_client_with_secret("test-secret")
    payload = b'{"test": "data"}'
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Signature": "invalidsignature",
            "X-Event-Type": "signed.event",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 401
    data = response.json()
    assert "Invalid HMAC signature" in data["detail"]


def test_receive_webhook_without_signature_when_required():
    """Test webhook rejection when signature is required but missing."""
    client = _get_client_with_secret("test-secret")
    payload = b'{"test": "data"}'
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Event-Type": "signed.event",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 401
    data = response.json()
    assert "Invalid HMAC signature" in data["detail"]


def test_github_style_signature():
    """Test GitHub-style sha256= prefix signature."""
    client = _get_client_with_secret("test-secret")
    payload = b'{"test": "data"}'
    signature = "sha256=" + hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Signature": signature,
            "X-Event-Type": "github.event",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


def test_secret_rotation():
    """Test multiple secrets for rotation."""
    client = _get_client_with_secret("old-secret,new-secret,current-secret")
    payload = b'{"rotation": "test"}'
    
    # Test with old secret
    signature = hmac.new(b"old-secret", payload, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Signature": signature,
            "X-Event-Type": "rotation.test",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    
    # Test with new secret
    signature = hmac.new(b"new-secret", payload, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Signature": signature,
            "X-Event-Type": "rotation.test2",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    
    # Test with current secret
    signature = hmac.new(b"current-secret", payload, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Signature": signature,
            "X-Event-Type": "rotation.test3",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200


def test_stats_endpoint():
    """Test stats endpoint."""
    client = _get_client_with_secret("test-secret")
    # Send a webhook first with valid signature
    payload = b'{"test": "stats"}'
    signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    client.post(
        "/webhook",
        content=payload,
        headers={"X-Event-Type": "stats.test", "Content-Type": "application/json", "X-Signature": signature}
    )
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_multiple_webhooks():
    """Test receiving multiple webhooks."""
    client = _get_client_with_secret("test-secret")
    for i in range(3):
        payload = f'{{"index": {i}}}'.encode()
        signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhook",
            content=payload,
            headers={"X-Event-Type": f"batch.{i}", "Content-Type": "application/json", "X-Signature": signature}
        )
        assert response.status_code == 200
    
    # Check health reflects all webhooks
    health = client.get("/health").json()
    assert health["queue"]["total"] >= 3


def test_webhook_queue_tracking():
    """Test webhook queue tracking."""
    client = _get_client_with_secret("test-secret")
    payload = b'{"track": "me"}'
    signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=payload,
        headers={"Content-Type": "application/json", "X-Signature": signature}
    )
    assert response.status_code == 200
    
    health = client.get("/health").json()
    assert health["queue"]["pending"] >= 1


def test_event_type_default():
    """Test default event type."""
    client = _get_client_with_secret("test-secret")
    payload = b'{"no": "header"}'
    signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=payload,
        headers={"Content-Type": "application/json", "X-Signature": signature}
    )
    assert response.status_code == 200


def test_stats_aggregation():
    """Test stats aggregation by event type."""
    client = _get_client_with_secret("test-secret")
    # Send webhooks with same event type
    for _ in range(2):
        payload = b'{"aggregation": "test"}'
        signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        client.post(
            "/webhook",
            content=payload,
            headers={"X-Event-Type": "agg.test", "Content-Type": "application/json", "X-Signature": signature}
        )
    
    stats = client.get("/stats").json()
    assert "agg.test" in stats or "generic" in stats


def test_strict_mode_rejects_unsigned():
    """Test strict mode rejects webhooks without signatures."""
    client = _get_client_with_secret("test-secret", strict="true")
    payload = b'{"test": "strict"}'
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={"X-Event-Type": "strict.test", "Content-Type": "application/json"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "Invalid HMAC signature" in data["detail"]


def test_strict_mode_allows_signed():
    """Test strict mode allows properly signed webhooks."""
    client = _get_client_with_secret("test-secret", strict="true")
    payload = b'{"test": "strict"}'
    signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-Signature": signature,
            "X-Event-Type": "strict.test",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"