from fastapi import FastAPI, Response, status, Query
import asyncpg
import os
from datetime import datetime
from typing import Optional, List

app = FastAPI(title="vantay-fastapi")
DATABASE_URL = os.getenv("DATABASE_URL")
POOL: Optional[asyncpg.Pool] = None

@app.on_event("startup")
async def startup():
    global POOL
    POOL = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, ssl=False)

@app.on_event("shutdown")
async def shutdown():
    if POOL:
        await POOL.close()

@app.get("/health")
async def health():
    return {"ok": True, "service": "fastapi", "time": datetime.utcnow().isoformat()}

@app.get("/db-check")
async def db_check(response: Response):
    try:
        async with POOL.acquire() as conn:
            row = await conn.fetchrow("select current_user, current_database(), now()")
        return {"ok": True, "db": dict(row)}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"ok": False, "error": str(e)}

# ---- USERS ----
@app.get("/api/users")
async def users_list():
    async with POOL.acquire() as conn:
        rows = await conn.fetch("select id, email, name, created_at, updated_at from app.users order by id desc limit 100")
        return {"items": [dict(r) for r in rows]}

@app.post("/api/users")
async def users_create(payload: dict, response: Response):
    email = payload.get("email")
    name = payload.get("name")
    if not email:
        response.status_code = 400
        return {"ok": False, "error": "email is required"}
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            "insert into app.users(email,name) values($1,$2) returning id,email,name,created_at,updated_at",
            email, name
        )
        return {"ok": True, "item": dict(row)}

# ---- CLIENTS ----
@app.get("/api/clients")
async def clients_list(user_id: int = Query(...)):
    async with POOL.acquire() as conn:
        rows = await conn.fetch(
            "select id,user_id,name,email,phone,created_at,updated_at from app.clients where user_id=$1 order by id desc limit 100",
            user_id
        )
        return {"items": [dict(r) for r in rows]}

@app.post("/api/clients")
async def clients_create(payload: dict, response: Response):
    user_id = payload.get("user_id")
    name = payload.get("name")
    email = payload.get("email")
    phone = payload.get("phone")
    if not user_id or not name:
        response.status_code = 400
        return {"ok": False, "error": "user_id and name are required"}
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            "insert into app.clients(user_id,name,email,phone) values($1,$2,$3,$4) returning id,user_id,name,email,phone,created_at,updated_at",
            int(user_id), name, email, phone
        )
        return {"ok": True, "item": dict(row)}

# ---- APPOINTMENTS ----
@app.get("/api/appointments")
async def appts_list(
    user_id: int = Query(...),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
):
    sql = """
      select a.id, a.user_id, a.client_id, a.start_at, a.end_at, a.status, a.title, a.notes,
             a.created_at, a.updated_at, c.name as client_name
      from app.appointments a
      left join app.clients c on c.id = a.client_id
      where a.user_id = $1
    """
    params: List = [user_id]
    if from_ts:
      sql += " and a.start_at >= $2" if len(params) == 1 else f" and a.start_at >= ${len(params)+1}"
      params.append(from_ts)
    if to_ts:
      sql += f" and a.start_at < ${len(params)+1}"
      params.append(to_ts)
    sql += " order by a.start_at desc limit 200"
    async with POOL.acquire() as conn:
        rows = await conn.fetch(sql, *params)
        return {"items": [dict(r) for r in rows]}

@app.post("/api/appointments")
async def appts_create(payload: dict, response: Response):
    required = ("user_id", "start_at", "end_at")
    if any(k not in payload for k in required):
        response.status_code = 400
        return {"ok": False, "error": "user_id, start_at, end_at are required"}
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            """insert into app.appointments(user_id,client_id,start_at,end_at,title,notes)
               values($1,$2,$3,$4,$5,$6)
               returning id,user_id,client_id,start_at,end_at,status,title,notes,created_at,updated_at""",
            int(payload["user_id"]), payload.get("client_id"),
            payload["start_at"], payload["end_at"],
            payload.get("title"), payload.get("notes")
        )
        return {"ok": True, "item": dict(row)}
