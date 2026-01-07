<coding_guidelines>
## AGENTS GUIDE (muxi-python)

Purpose: fast orientation for AI coding agents contributing to the Python SDK.

### Project structure
```
python/
├── muxi/
│   ├── __init__.py         # Package exports
│   ├── server.py           # ServerClient, AsyncServerClient (HMAC auth)
│   ├── formation.py        # FormationClient, AsyncFormationClient (key auth)
│   ├── transport.py        # httpx-based HTTP transport, retries
│   ├── auth.py             # HMAC signature generation
│   ├── errors.py           # Typed error hierarchy
│   └── version.py          # SDK version
├── tests/
│   ├── test_*.py           # Unit tests
│   └── test_integration*.py # Integration tests (need env vars)
├── pyproject.toml          # Package metadata, dependencies
├── AGENTS.md
├── USER_GUIDE.md
└── README.md
```

### Quick commands
```bash
cd python
pip install -e ".[dev]"    # Install in dev mode
pytest tests/              # Run tests
pytest tests/test_integration.py  # Integration tests (need MUXI_SDK_E2E_* env vars)
black muxi/ tests/         # Format code
```

### Key patterns
- **Sync + Async**: Every client has sync (`ServerClient`) and async (`AsyncServerClient`) variants
- **httpx transport**: Connection pooling, native async, structured timeouts
- **ServerClient**: HMAC auth with `key_id`/`secret_key` for `/rpc` endpoints
- **FormationClient**: `X-MUXI-CLIENT-KEY` or `X-MUXI-ADMIN-KEY` headers
- **Streaming**: Returns generators (sync) or async generators (async)
- **Retries**: Exponential backoff on 429/5xx, respects `Retry-After`
- **Idempotency**: Auto `X-Muxi-Idempotency-Key` on every request

### Adding new endpoints
1. Add method to `FormationClient` and `AsyncFormationClient` in `formation.py`
2. Follow existing pattern: sync method calls `_request()`, async calls `_arequest()`
3. For streaming, use `_stream_sse()` or `_astream_sse()`
4. Run tests before committing

### Context managers
Both sync and async clients support context managers:
```python
with FormationClient(...) as client:
    client.health()

async with AsyncFormationClient(...) as client:
    await client.health()
```

### Git workflow
```bash
cd python
git status --short
git add . && git commit -m "..."
git push origin develop
# Then from sdks root: git add python && git commit -m "Update python submodule"
```

### Rules
- Keep idempotency header on every request — no toggles
- Streaming uses infinite timeouts
- Strip whitespace from keys (`.strip()`) to avoid header errors
- Do not add dependencies without approval
- Do not edit README unless requested
- Format with `black` before committing
</coding_guidelines>
