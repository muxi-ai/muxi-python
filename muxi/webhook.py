"""
Webhook signature verification and payload parsing for MUXI async webhooks.

Usage:
    from muxi import webhook

    @app.post("/webhooks/muxi")
    async def handle(request: Request):
        payload = await request.body()
        signature = request.headers.get("X-Muxi-Signature")

        if not webhook.verify_signature(payload, signature, WEBHOOK_SECRET):
            raise HTTPException(401, "Invalid signature")

        event = webhook.parse(payload)
        print(event.request_id, event.status, event.content)
"""

import hmac
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class ContentItem:
    """A content item in the webhook response."""

    type: str
    text: Optional[str] = None
    file: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentItem":
        return cls(
            type=data.get("type", "text"),
            text=data.get("text"),
            file=data.get("file"),
        )


@dataclass
class ErrorDetails:
    """Error details when webhook status is 'failed'."""

    code: str
    message: str
    trace: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorDetails":
        return cls(
            code=data.get("code", "unknown"),
            message=data.get("message", "Unknown error"),
            trace=data.get("trace"),
        )


@dataclass
class Clarification:
    """Clarification details when status is 'awaiting_clarification'."""

    question: str
    clarification_request_id: Optional[str] = None
    original_message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clarification":
        return cls(
            question=data.get("clarification_question", ""),
            clarification_request_id=data.get("clarification_request_id"),
            original_message=data.get("original_message"),
        )


@dataclass
class WebhookEvent:
    """Parsed webhook event from MUXI async completion."""

    request_id: str
    status: str  # "completed" | "failed" | "awaiting_clarification"
    timestamp: int
    content: List[ContentItem] = field(default_factory=list)
    error: Optional[ErrorDetails] = None
    clarification: Optional[Clarification] = None
    formation_id: Optional[str] = None
    user_id: Optional[str] = None
    processing_time: Optional[float] = None
    processing_mode: str = "async"
    webhook_url: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebhookEvent":
        content = []
        response_data = data.get("response") or []
        for item in response_data:
            content.append(ContentItem.from_dict(item))

        error = None
        if data.get("error"):
            error = ErrorDetails.from_dict(data["error"])

        clarification = None
        if data.get("status") == "awaiting_clarification":
            clarification = Clarification.from_dict(data)

        return cls(
            request_id=data.get("id", ""),
            status=data.get("status", "unknown"),
            timestamp=data.get("timestamp", 0),
            content=content,
            error=error,
            clarification=clarification,
            formation_id=data.get("formation_id"),
            user_id=data.get("user_id"),
            processing_time=data.get("processing_time"),
            processing_mode=data.get("processing_mode", "async"),
            webhook_url=data.get("webhook_url"),
            raw=data,
        )


def verify_signature(
    payload: Union[bytes, str],
    signature_header: Optional[str],
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verify webhook signature and check timestamp to prevent replay attacks.

    Args:
        payload: Raw request body (bytes or string)
        signature_header: Value of X-Muxi-Signature header (format: "t=timestamp,v1=signature")
        secret: Webhook secret (typically admin_key or dedicated webhook secret)
        tolerance_seconds: Maximum age of webhook in seconds (default 5 minutes)

    Returns:
        True if signature is valid, False otherwise

    Raises:
        WebhookVerificationError: If signature format is invalid or verification fails

    Example:
        from muxi import webhook

        payload = await request.body()
        signature = request.headers.get("X-Muxi-Signature")

        if not webhook.verify_signature(payload, signature, WEBHOOK_SECRET):
            raise HTTPException(401, "Invalid signature")
    """
    if not signature_header:
        return False

    if not secret:
        raise WebhookVerificationError("Webhook secret is required")

    # Parse signature header: "t=1234567890,v1=abc123..."
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(","))
        timestamp_str = parts.get("t")
        signature = parts.get("v1")

        if not timestamp_str or not signature:
            return False

        timestamp = int(timestamp_str)
    except (ValueError, KeyError):
        return False

    # Check timestamp tolerance (prevent replay attacks)
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance_seconds:
        return False

    # Normalize payload to bytes
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    # Compute expected signature: HMAC-SHA256(secret, "timestamp.payload")
    message = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected, signature)


def parse(payload: Union[bytes, str, Dict[str, Any]]) -> WebhookEvent:
    """
    Parse webhook payload into a typed WebhookEvent object.

    Args:
        payload: Raw request body (bytes, string, or already-parsed dict)

    Returns:
        WebhookEvent with typed fields for easy access

    Raises:
        WebhookVerificationError: If payload cannot be parsed

    Example:
        from muxi import webhook

        event = webhook.parse(payload)

        if event.status == "completed":
            for item in event.content:
                if item.type == "text":
                    print(item.text)
        elif event.status == "failed":
            print(f"Error: {event.error.message}")
        elif event.status == "awaiting_clarification":
            print(f"Question: {event.clarification.question}")
    """
    if isinstance(payload, dict):
        data = payload
    elif isinstance(payload, bytes):
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise WebhookVerificationError(f"Invalid JSON payload: {e}")
    elif isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise WebhookVerificationError(f"Invalid JSON payload: {e}")
    else:
        raise WebhookVerificationError(f"Unsupported payload type: {type(payload)}")

    return WebhookEvent.from_dict(data)
