# MUXI Python SDK

Official Python SDK for [MUXI](https://muxi.org) — infrastructure for AI agents.

**Highlights**
- Sync & async clients with pooled `httpx` transport
- Context managers for automatic client cleanup
- Built-in retries, idempotency, and typed errors
- Streaming helpers for chat/audio and deploy/log tails

> Need deeper usage notes? See the [User Guide](https://github.com/muxi-ai/muxi-python/blob/main/USER_GUIDE.md) for streaming, retries, and auth details.

## Installation

```bash
pip install muxi-client
```

## Quick Start (sync)

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

## Quick Start (async)

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

## Formation base URL override

- Default (via server proxy): `server_url + /api/{formation_id}/v1`
- Direct formation: set `base_url="http://localhost:9012/v1"` (or use `url` for dev mode `http://localhost:8001/v1`)

## Auth & headers

- Server: HMAC with `key_id`/`secret_key` on `/rpc/*`.
- Formation: `X-MUXI-CLIENT-KEY` or `X-MUXI-ADMIN-KEY` on formation API.
- Idempotency: `X-Muxi-Idempotency-Key` auto-generated on every request.
- SDK: `X-Muxi-SDK`, `X-Muxi-Client` headers set automatically.

## Streaming

- Chat/audio: POST `/chat` or `/audiochat` with `stream=True`; consume SSE events.
- Deploy/log streams: methods return generators/async generators.

## Errors, retries, timeouts

- Typed errors for auth/validation/rate-limit/server/connection.
- Default timeout 30s (streaming is unbounded); retries on 429/5xx/connection with backoff.
