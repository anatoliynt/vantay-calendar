from fastapi import FastAPI, Response, status
import asyncpg
import os
from datetime import datetime

app = FastAPI(title="vantay-fastapi")
DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/health")
async def health():
    return {"ok": True, "service": "fastapi", "time": datetime.utcnow().isoformat()}

@app.get("/db-check")
async def db_check(response: Response):
    try:
        conn = await asyncpg.connect(DATABASE_URL, ssl=False)
        row = await conn.fetchrow("select current_user, current_database(), now()")
        await conn.close()
        return {"ok": True, "db": dict(row)}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"ok": False, "error": str(e)}
