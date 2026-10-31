"""Pydantic models."""

from pydantic import BaseModel

class WebhookPayload(BaseModel):
    """Webhook payload model."""
    event_type: str
    data: dict
