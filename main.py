from fastapi import FastAPI, Request, Depends
import httpx
from contextlib import asynccontextmanager
from schemas import OpenAI
from config import settings
from auth import get_current_client
from quota import check_quota

@asynccontextmanager
async def lifespan(app : FastAPI):
    app.state.http_client = httpx.AsyncClient(
        base_url="https://api.openai.com",
        headers= {"Authorization":f"Bearer {settings.openai_api_key}"},
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=30)
    )
    yield
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)

@app.post("/v1/chat/completions")
async def completion(request : Request,  body: OpenAI, current_client = Depends(get_current_client), check = Depends(check_quota)):
    client = request.app.state.http_client
    response = await client.post(
        "v1/chat/completions",
        json=body.model_dump(exclude_none=True),
    )

    return response.json()

