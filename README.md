# MUXI Python SDK

Official Python SDK for [MUXI](https://muxi.org) - the infrastructure layer for AI agents.

> Need deeper usage notes? See [USER_GUIDE.md](./USER_GUIDE.md) for streaming, retries, and auth details.

## Installation

```bash
pip install muxi-client
```

## Quick Start (sync)

```python
from muxi import ServerClient, ServerConfig, FormationClient, FormationConfig

server = ServerClient(ServerConfig(
    url="https://server.example.com",
    key_id="<key_id>",
    secret_key="<secret_key>",
))
print(server.status())

formation = FormationClient(FormationConfig(
    server_url="https://server.example.com",
    formation_id="<formation_id>",
    client_key="<client_key>",
    admin_key="<admin_key>",
))
print(formation.health())
```

## Quick Start (async)

```python
import asyncio
from muxi import AsyncServerClient, ServerConfig, AsyncFormationClient, FormationConfig

async def main():
    server = AsyncServerClient(ServerConfig(
        url="https://server.example.com",
        key_id="<key_id>",
        secret_key="<secret_key>",
    ))
    print(await server.status())

    formation = AsyncFormationClient(FormationConfig(
        server_url="https://server.example.com",
        formation_id="<formation_id>",
        client_key="<client_key>",
        admin_key="<admin_key>",
    ))
    async for evt in await formation.chat_stream({"message": "hi"}):
        print(evt)
        break

asyncio.run(main())
```

## Formation Base URL override

- Default (via server proxy): `server_url + /api/{formation_id}/v1`
- Direct formation: set `base_url="http://localhost:9012/v1"` (or use `url` for dev mode `http://localhost:8001/v1`)

## Auth & Headers

- Server: HMAC with `key_id`/`secret_key` on `/rpc/*`.
- Formation: `X-MUXI-CLIENT-KEY` or `X-MUXI-ADMIN-KEY` on formation API.
- Idempotency: `X-Muxi-Idempotency-Key` auto-generated on every request.
- SDK: `X-Muxi-SDK`, `X-Muxi-Client` headers set automatically.

## Streaming

- Chat/audio: POST `/chat` or `/audiochat` with `stream=True`; consume SSE events.
- Deploy/log streams: methods return generators/async generators.

## Errors, Retries, Timeouts

- Typed errors for auth/validation/rate-limit/server/connection.
- Default timeout 30s (streaming is unbounded); retries on 429/5xx/connection with backoff.
