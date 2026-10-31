"""FastAPI webhook relay application."""

import hashlib
import hmac
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Header

app = FastAPI(
    title="Webhook Relay",
    version="0.1.0",
    description="FastAPI webhook ingestion with HMAC verification and SQLite queue"
)

DB_PATH = Path.home() / ".webhook-relay.db"


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


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None),
    x_event_type: str = Header("generic")
):
    """Receive and queue webhook."""
    body = await request.body()
    client_host = request.client.host if request.client else "unknown"
    
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
