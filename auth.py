import asyncpg
import hashlib
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings

security = HTTPBearer()

async def get_current_client(credentials: HTTPAuthorizationCredentials = Depends(security)):
    raw_key = credentials.credentials

    conn = await asyncpg.connect(
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
    )

    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

    row = await conn.fetchrow("SELECT * FROM clients WHERE hashed_key = $1", hashed_key)

    await conn.close()

    if row is None:
        raise HTTPException()    

    return row
