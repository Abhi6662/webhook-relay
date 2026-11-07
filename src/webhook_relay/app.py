"""FastAPI webhook relay application."""

import hashlib
import hmac
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Header, HTTPException

app = FastAPI(
    title="Webhook Relay",
    version="0.2.0",
    description="FastAPI webhook ingestion with HMAC verification and SQLite queue"
)

DB_PATH = Path.home() / ".webhook-relay.db"

# HMAC secret from environment (supports multiple secrets for rotation)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_SECRETS = [s.strip() for s in WEBHOOK_SECRET.split(",") if s.strip()]

# Strict mode: if True and secret is configured, reject webhooks without signatures
WEBHOOK_STRICT_MODE = os.getenv("WEBHOOK_STRICT_MODE", "false").lower() == "true"


def _init_db() -> None:
    """Initialize SQLite database with WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            signature TEXT,
            source_ip TEXT,
            received_at REAL NOT NULL,
            processed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


_init_db()


def _verify_signature(payload: bytes, signature: str, secrets: list[str]) -> bool:
    """
    Verify HMAC-SHA256 signature against multiple secrets (for rotation).
    
    Args:
        payload: Raw request body bytes
        signature: Signature from X-Signature header (hex encoded)
        secrets: List of secret keys to try
        
    Returns:
        True if any secret validates the signature
    """
    if not secrets:
        return True  # No secret configured, skip verification
    
    if not signature:
        return False  # Signature required when secrets configured
    
    # Remove 'sha256=' prefix if present (GitHub style)
    if signature.startswith("sha256="):
        signature = signature[7:]
    
    for secret in secrets:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature):
            return True
    
    return False


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None),
    x_event_type: str = Header("generic")
):
    """Receive and queue webhook with HMAC verification."""
    body = await request.body()
    client_host = request.client.host if request.client else "unknown"
    
    # Verify HMAC signature if secrets are configured
    if WEBHOOK_SECRETS:
        if not _verify_signature(body, x_signature or "", WEBHOOK_SECRETS):
            raise HTTPException(
                status_code=401,
                detail="Invalid HMAC signature"
            )
    elif WEBHOOK_STRICT_MODE and x_signature is None:
        # Strict mode but no secret configured - reject unsigned webhooks
        raise HTTPException(
            status_code=401,
            detail="Signature required in strict mode"
        )
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """INSERT INTO webhooks (event_type, payload, signature, source_ip, received_at)
           VALUES (?, ?, ?, ?, ?)""",
        (x_event_type, body.decode(), x_signature or "", client_host, time.time())
    )
    webhook_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"status": "received", "id": webhook_id}


@app.get("/health")
async def health():
    """Health check with queue stats."""
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM webhooks WHERE processed = 0").fetchone()[0]
    conn.close()
    
    return {
        "status": "ok",
        "queue": {
            "total": total,
            "pending": pending,
            "processed": total - pending
        }
    }


@app.get("/stats")
async def stats():
    """Delivery statistics by event type."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT event_type, COUNT(*) as count, 
               SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) as processed_count
        FROM webhooks
        GROUP BY event_type
    """)
    
    results = {}
    for row in cursor.fetchall():
        results[row[0]] = {
            "total": row[1],
            "processed": row[2],
            "pending": row[1] - row[2]
        }
    
    conn.close()
    return results


@app.get("/metrics")
async def metrics():
    """Prometheus-style metrics."""
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM webhooks WHERE processed = 0").fetchone()[0]
    conn.close()
    
    return {
        "webhooks_total": total,
        "webhooks_pending": pending,
        "webhooks_processed": total - pending
    }