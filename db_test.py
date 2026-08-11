import asyncio
import asyncpg
from config import settings

async def main():
    conn = await asyncpg.connect(
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
    )

    result = await conn.fetch("SELECT 1")
    print(result)
    await conn.close()

asyncio.run(main())