# MUXI Python SDK User Guide

## Installation

```bash
pip install muxi-client
```

## Quickstart (sync)

```python
from muxi import ServerClient, FormationClient

server = ServerClient(
    url="https://server.example.com",
    key_id="<key_id>",
    secret_key="<secret_key>",
)
print(server.status())

formation = FormationClient(
    server_url="https://server.example.com",
    formation_id="<formation_id>",
    client_key="<client_key>",
    admin_key="<admin_key>",
)
print(formation.health())
```

## Quickstart (async)

```python
import asyncio
from muxi import AsyncServerClient, AsyncFormationClient

async def main():
    server = AsyncServerClient(
        url="https://server.example.com",
        key_id="<key_id>",
        secret_key="<secret_key>",
    )
    print(await server.status())

    formation = AsyncFormationClient(
        server_url="https://server.example.com",
        formation_id="<formation_id>",
        client_key="<client_key>",
        admin_key="<admin_key>",
    )
    async for evt in await formation.chat_stream({"message": "hi"}):
        print(evt)
        break

asyncio.run(main())
```

## Auth & Headers

- Server: HMAC with `key_id`/`secret_key` on `/rpc` endpoints.
- Formation: `X-MUXI-CLIENT-KEY` or `X-MUXI-ADMIN-KEY` on `/api/{formation}/v1` (default); override `base_url` for direct access (e.g., `http://localhost:9012/v1`).
- Idempotency: `X-Muxi-Idempotency-Key` auto-generated on every request.
- SDK: `X-Muxi-SDK`, `X-Muxi-Client` headers set automatically.

## Timeouts, Retries, Debug

- Default timeout: 30s (no timeout for streaming).
- Retries: `max_retries` (exponential backoff) on 429/5xx/connection errors.
- Debug logging enabled when `debug=True` or `MUXI_DEBUG` is set.

## Streaming

- Chat/audio: POST `/chat` or `/audiochat` with `stream=True`; consume SSE events.
- Deploy/log streams: use corresponding methods returning generators/async generators.

## Error Handling

- Non-2xx raise typed errors (AuthenticationError, AuthorizationError, NotFoundError, ValidationError, RateLimitError, ServerError, ConnectionError) with `code`, `message`, `status_code` and optional `retry_after`.
- Responses unwrap envelopes and include `request_id` and `timestamp` when provided.

## Pagination

- Endpoints using `limit`/`has_more` return the raw response; pass `limit` as needed.

## Webhook Verification

For async operations, MUXI delivers results via webhooks. The SDK provides helpers to verify signatures and parse payloads.

```python
from muxi import webhook

@app.post("/webhooks/muxi")
async def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Muxi-Signature")

    # Verify signature (returns False if invalid)
    if not webhook.verify_signature(payload, signature, WEBHOOK_SECRET):
        raise HTTPException(401, "Invalid signature")

    # Parse into typed object
    event = webhook.parse(payload)

    if event.status == "completed":
        for item in event.content:
            if item.type == "text":
                print(item.text)
    elif event.status == "failed":
        print(f"Error: {event.error.message}")
    elif event.status == "awaiting_clarification":
        print(f"Question: {event.clarification.question}")

    return {"status": "received"}
```

### Webhook Functions

| Function | Description |
|----------|-------------|
| `webhook.verify_signature(payload, signature, secret, tolerance=300)` | Verify HMAC-SHA256 signature and timestamp |
| `webhook.parse(payload)` | Parse payload into `WebhookEvent` object |

### WebhookEvent Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | str | Original request ID |
| `status` | str | "completed", "failed", or "awaiting_clarification" |
| `timestamp` | int | Unix timestamp |
| `content` | List[ContentItem] | Response content items |
| `error` | ErrorDetails | Error info (if failed) |
| `clarification` | Clarification | Clarification details (if awaiting) |
| `processing_time` | float | Processing duration in seconds |
| `raw` | dict | Original payload for custom access |

## Examples

- See `examples/server_status.py` and `examples/formation_health.py` for minimal usage.
