from fastapi import HTTPException, Depends
from auth import get_current_client

def check_quota(current_client = Depends(get_current_client)):
    if current_client['tokens_used'] >= current_client['quota_limit']:
        raise HTTPException(status_code=429, detail="Quota Exceeded")
    
async def update_usage(pool,user_id: int, tokens: int):

    await pool.execute(
        "UPDATE clients SET tokens_used = tokens_used + $1 WHERE user_id = $2",
        tokens, user_id,
    )
