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

## Examples

- See `examples/server_status.py` and `examples/formation_health.py` for minimal usage.
