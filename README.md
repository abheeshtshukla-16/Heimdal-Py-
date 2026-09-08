# Heimdalll

A lightweight LLM gateway: authenticates clients, enforces per-client usage quotas, and proxies chat completions to OpenAI and Anthropic behind one consistent, OpenAI-shaped API.

## Features

- **Auth** — bearer-token clients, hashed (SHA-256) and looked up against Postgres. No server-side sessions; every request re-validates from scratch.
- **Quota enforcement** — soft per-client token quota. Checks and increments hit Redis only (`INCRBY`, cache-aside on read); a background task flushes dirty counters to Postgres every 10s, so quota enforcement never adds a Postgres round-trip to the request path.
- **OpenAI-compatible chat completions** — `POST /v1/chat/completions`, both streaming (SSE) and non-streaming.
- **Multi-provider routing** — a request naming a `claude*` model is translated to Anthropic's `/v1/messages` wire format and its response translated back; everything else goes to OpenAI. Routing today is a single model-name check, not a full rule/config table yet.
- `GET /health` — plain liveness check, no auth.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

1. Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and the Postgres credentials.
2. Start Postgres and Redis: `docker compose up -d`
3. Create the `clients` table (see `schemas.sql`) against the running Postgres instance.
4. Install dependencies: `uv sync`
5. Seed a client and get an API key (printed once, not recoverable after): `uv run seed_client.py`
6. Run the gateway: `uv run uvicorn main:app --reload`

## Usage

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <key from seed_client.py>" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}'
```

Use a `claude-*` model name (e.g. `claude-opus-4`) in the same request shape to route to Anthropic instead — the request/response format the caller sees doesn't change.

## Known limitations

- Quota is soft — a request already in flight when a client crosses their limit still completes; exact cost is only known once the provider responds.
- Upstream errors (rate limits, outages) are currently passed through unmodified rather than normalized into a consistent shape.
- No persistence configured on the Redis container, so a crash loses whatever usage hasn't been flushed to Postgres yet (up to ~10s).
- No tool-use / function-calling support in the Anthropic adapter yet — plain chat completions only.
