from fastapi import FastAPI, Request, Depends
import httpx
import json
import asyncpg
from contextlib import asynccontextmanager
from schemas import OpenAI
from config import settings
from auth import get_current_client
from quota import check_quota, update_usage
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
    yield
    await app.state.http_client.aclose()
    await app.state.pg_pool.close()

app = FastAPI(lifespan=lifespan)

@app.post("/v1/chat/completions")
async def completion(request : Request,  body: OpenAI, current_client = Depends(get_current_client), check = Depends(check_quota)):
    client = request.app.state.http_client
    payload = body.model_dump(exclude_none=True)
    if body.stream:
        payload["stream_options"] = {"include_usage": True};
        return StreamingResponse(stream_completion(client, payload, request.app.state.pg_pool, current_client['user_id']), media_type="text/event-stream")
    response = await client.post(
        "v1/chat/completions",
        json=payload,
    )
    result = response.json()
    await update_usage(request.app.state.pg_pool ,current_client['user_id'], result['usage']['total_tokens'])

    return result

async def stream_completion(client, payload, pool, user_id):
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
            await update_usage(pool, user_id, usage["total_tokens"])

