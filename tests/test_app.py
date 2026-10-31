"""Tests for webhook relay app."""

import hashlib
import hmac
from fastapi.testclient import TestClient
from webhook_relay import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "queue" in data


def test_receive_webhook_without_signature():
    """Test webhook reception without signature."""
    response = client.post(
        "/webhook",
        json={"test": "data"},
        headers={"X-Event-Type": "test.event"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "id" in data


def test_receive_webhook_with_signature():
    """Test webhook reception with HMAC signature."""
    payload = b'{"test": "data"}'
    secret = "test-secret"
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/webhook",
        data=payload,
        headers={
            "X-Signature": signature,
            "X-Event-Type": "signed.event",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


def test_stats_endpoint():
    """Test stats endpoint."""
    # Send a webhook first
    client.post(
        "/webhook",
        json={"test": "stats"},
        headers={"X-Event-Type": "stats.test"}
    )
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_multiple_webhooks():
    """Test receiving multiple webhooks."""
    for i in range(3):
        response = client.post(
            "/webhook",
            json={"index": i},
            headers={"X-Event-Type": f"batch.{i}"}
        )
        assert response.status_code == 200
    
    # Check health reflects all webhooks
    health = client.get("/health").json()
    assert health["queue"]["total"] >= 3


def test_webhook_queue_tracking():
    """Test webhook queue tracking."""
    response = client.post("/webhook", json={"track": "me"})
    assert response.status_code == 200
    
    health = client.get("/health").json()
    assert health["queue"]["pending"] >= 1


def test_event_type_default():
    """Test default event type."""
    response = client.post("/webhook", json={"no": "header"})
    assert response.status_code == 200


def test_stats_aggregation():
    """Test stats aggregation by event type."""
    # Send webhooks with same event type
    for _ in range(2):
        client.post(
            "/webhook",
            json={"aggregation": "test"},
            headers={"X-Event-Type": "agg.test"}
        )
    
    stats = client.get("/stats").json()
    assert "agg.test" in stats or "generic" in stats
