import asyncio
import asyncpg
import hashlib
import secrets
from config import settings

async def main():
    raw_key = secrets.token_urlsafe(32)
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

    conn = await asyncpg.connect(
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
    )

    await conn.execute(
        "INSERT INTO clients (hashed_key, quota_limit) VALUES ($1, $2)",
        hashed_key, 1000,
    )

    await conn.close()

    print("Client created. Save this raw key now — it will never be shown again:")
    print(raw_key)

asyncio.run(main())
