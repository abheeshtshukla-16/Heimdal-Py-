import hashlib
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_client(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    raw_key = credentials.credentials
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

    row = await request.app.state.pg_pool.fetchrow(
        "SELECT * FROM clients WHERE hashed_key = $1", hashed_key
    )
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid API key");

    return row
