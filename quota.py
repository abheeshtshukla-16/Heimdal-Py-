import asyncio
from fastapi import HTTPException, Depends, Request
from auth import get_current_client

USAGE_KEY_PREFIX = "usage:"
DIRTY_USAGE_SET = "dirty_usage_clients"
FLUSH_INTERVAL_SECONDS = 10


async def _get_cached_usage(redis_client, current_client) -> int:
    key = f"{USAGE_KEY_PREFIX}{current_client['user_id']}"
    cached = await redis_client.get(key)
    if cached is not None:
        return int(cached)

    tokens_used = current_client["tokens_used"]
    await redis_client.set(key, tokens_used)
    return tokens_used


async def check_quota(request: Request, current_client = Depends(get_current_client)):
    usage = await _get_cached_usage(request.app.state.redis, current_client)
    if usage >= current_client['quota_limit']:
        raise HTTPException(status_code=429, detail="Quota Exceeded")


async def update_usage(redis_client, user_id: int, tokens: int):
    await redis_client.incrby(f"{USAGE_KEY_PREFIX}{user_id}", tokens)
    await redis_client.sadd(DIRTY_USAGE_SET, user_id)


async def flush_usage_to_postgres(pool, redis_client):
    while True:
        await asyncio.sleep(FLUSH_INTERVAL_SECONDS)

        dirty_user_ids = await redis_client.smembers(DIRTY_USAGE_SET)
        if not dirty_user_ids:
            continue

        for raw_user_id in dirty_user_ids:
            tokens = await redis_client.get(f"{USAGE_KEY_PREFIX}{raw_user_id}")
            if tokens is None:
                continue
            await pool.execute(
                "UPDATE clients SET tokens_used = $1 WHERE user_id = $2",
                int(tokens), int(raw_user_id),
            )

        await redis_client.srem(DIRTY_USAGE_SET, *dirty_user_ids)
