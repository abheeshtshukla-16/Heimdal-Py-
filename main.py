from fastapi import FastAPI, Request, Depends
import asyncio
import httpx
import json
import asyncpg
import redis.asyncio as redis
from contextlib import asynccontextmanager
from schemas import OpenAI
from config import settings
from auth import get_current_client
from quota import check_quota, update_usage, flush_usage_to_postgres
from anthropic_provider import build_anthropic_request, anthropic_to_openai_response, stream_anthropic_completion
from fastapi.responses import StreamingResponse

@asynccontextmanager
async def lifespan(app : FastAPI):
    app.state.http_client = httpx.AsyncClient(
        base_url="https://api.openai.com",
        headers= {"Authorization":f"Bearer {settings.openai_api_key}"},
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=30)
    )

    app.state.pg_pool = await asyncpg.create_pool(
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
    )

    app.state.anthropic_client = httpx.AsyncClient(
        base_url="https://api.anthropic.com",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
        },
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=30)
    )

    app.state.redis = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )

    app.state.usage_flush_task = asyncio.create_task(
        flush_usage_to_postgres(app.state.pg_pool, app.state.redis)
    )

    yield

    app.state.usage_flush_task.cancel()
    try:
        await app.state.usage_flush_task
    except asyncio.CancelledError:
        pass

    await app.state.http_client.aclose()
    await app.state.anthropic_client.aclose()
    await app.state.pg_pool.close()
    await app.state.redis.aclose()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/v1/chat/completions")
async def completion(request : Request,  body: OpenAI, current_client = Depends(get_current_client), check = Depends(check_quota)):
    if body.model.lower().startswith("claude"):
        client = request.app.state.anthropic_client
        payload = build_anthropic_request(body)
        if body.stream:
            return StreamingResponse(stream_anthropic_completion(client, payload, request.app.state.redis, current_client['user_id']), media_type="text/event-stream")
        response = await client.post("/v1/messages", json=payload)
        result = anthropic_to_openai_response(response.json())
        await update_usage(request.app.state.redis, current_client['user_id'], result['usage']['total_tokens'])
        return result

    client = request.app.state.http_client
    payload = body.model_dump(exclude_none=True)
    if body.stream:
        payload["stream_options"] = {"include_usage": True};
        return StreamingResponse(stream_completion(client, payload, request.app.state.redis, current_client['user_id']), media_type="text/event-stream")
    response = await client.post(
        "v1/chat/completions",
        json=payload,
    )
    result = response.json()
    await update_usage(request.app.state.redis, current_client['user_id'], result['usage']['total_tokens'])

    return result

async def stream_completion(client, payload, redis_client, user_id):
    usage = None
    async with client.stream("POST", "v1/chat/completions", json=payload) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                json_text = line.removeprefix("data: ")
                data = json.loads(json_text)
                if data.get("usage") is not None:
                    usage = data.get("usage")
            yield  line + "\n\n"
        if usage:
            await update_usage(redis_client, user_id, usage["total_tokens"])
