from fastapi import FastAPI, Response, status, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import os
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, EmailStr, field_validator

app = FastAPI(title="vantay-fastapi")
DATABASE_URL = os.getenv("DATABASE_URL")
POOL: Optional[asyncpg.Pool] = None

# CORS (на будущее фронту; при желании сузьте список)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cl.vantay.ru", "https://sub.vantay.ru", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ---------- MODELS ----------
class ClientIn(BaseModel):
    user_id: int
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class ClientOut(ClientIn):
    id: int
    created_at: datetime
    updated_at: datetime

class AppointmentIn(BaseModel):
    user_id: int
    client_id: Optional[int] = None
    start_at: datetime
    end_at: datetime
    status: Literal["scheduled", "canceled", "done"] = "scheduled"
    title: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("end_at")
    @classmethod
    def validate_time(cls, v, info):
        start_at = info.data.get("start_at")
        if start_at and v <= start_at:
            raise ValueError("end_at must be greater than start_at")
        return v

class AppointmentOut(AppointmentIn):
    id: int
    created_at: datetime
    updated_at: datetime
    client_name: Optional[str] = None

# ---------- CLIENTS ----------
@app.get("/api/clients")
async def clients_list(user_id: int = Query(...), limit: int = Query(100, ge=1, le=500)):
    async with POOL.acquire() as conn:
        rows = await conn.fetch(
            "select id, user_id, name, email, phone, created_at, updated_at "
            "from app.clients where user_id=$1 order by id desc limit $2",
            user_id, limit
        )
        return {"items": [dict(r) for r in rows]}

@app.post("/api/clients")
async def clients_create(payload: ClientIn):
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            "insert into app.clients(user_id,name,email,phone) values($1,$2,$3,$4) "
            "returning id,user_id,name,email,phone,created_at,updated_at",
            payload.user_id, payload.name, payload.email, payload.phone
        )
        return {"ok": True, "item": dict(row)}

@app.put("/api/clients/{client_id}")
async def clients_update(client_id: int, payload: ClientIn):
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            "update app.clients set name=$1, email=$2, phone=$3 "
            "where id=$4 and user_id=$5 "
            "returning id,user_id,name,email,phone,created_at,updated_at",
            payload.name, payload.email, payload.phone, client_id, payload.user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="client not found")
        return {"ok": True, "item": dict(row)}

@app.delete("/api/clients/{client_id}")
async def clients_delete(client_id: int, user_id: int = Query(...)):
    async with POOL.acquire() as conn:
        r = await conn.execute("delete from app.clients where id=$1 and user_id=$2", client_id, user_id)
        if r.split()[-1] == "0":
            raise HTTPException(status_code=404, detail="client not found")
        return {"ok": True}

# ---------- APPOINTMENTS ----------
@app.get("/api/appointments")
async def appts_list(user_id: int = Query(...), limit: int = Query(100, ge=1, le=500)):
    async with POOL.acquire() as conn:
        rows = await conn.fetch(
            "select a.id, a.user_id, a.client_id, a.start_at, a.end_at, a.status, "
            "a.title, a.notes, a.created_at, a.updated_at, c.name as client_name "
            "from app.appointments a "
            "left join app.clients c on c.id = a.client_id "
            "where a.user_id=$1 "
            "order by a.start_at desc limit $2",
            user_id, limit
        )
        return {"items": [dict(r) for r in rows]}

@app.post("/api/appointments")
async def appts_create(payload: AppointmentIn, response: Response):
    # если указан client_id — убедимся, что он принадлежит тому же user_id
    async with POOL.acquire() as conn:
        if payload.client_id is not None:
            owner = await conn.fetchval("select user_id from app.clients where id=$1", payload.client_id)
            if owner is None or owner != payload.user_id:
                response.status_code = 400
                return {"ok": False, "error": "client_id does not belong to user_id"}

        row = await conn.fetchrow(
            "insert into app.appointments(user_id,client_id,start_at,end_at,status,title,notes) "
            "values($1,$2,$3,$4,$5,$6,$7) "
            "returning id,user_id,client_id,start_at,end_at,status,title,notes,created_at,updated_at",
            payload.user_id, payload.client_id, payload.start_at, payload.end_at,
            payload.status, payload.title, payload.notes
        )
        return {"ok": True, "item": dict(row)}

@app.put("/api/appointments/{appt_id}")
async def appts_update(appt_id: int, payload: AppointmentIn, response: Response):
    async with POOL.acquire() as conn:
        if payload.client_id is not None:
            owner = await conn.fetchval("select user_id from app.clients where id=$1", payload.client_id)
            if owner is None or owner != payload.user_id:
                response.status_code = 400
                return {"ok": False, "error": "client_id does not belong to user_id"}

        row = await conn.fetchrow(
            "update app.appointments "
            "set client_id=$1, start_at=$2, end_at=$3, status=$4, title=$5, notes=$6 "
            "where id=$7 and user_id=$8 "
            "returning id,user_id,client_id,start_at,end_at,status,title,notes,created_at,updated_at",
            payload.client_id, payload.start_at, payload.end_at, payload.status,
            payload.title, payload.notes, appt_id, payload.user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="appointment not found")
        return {"ok": True, "item": dict(row)}

@app.delete("/api/appointments/{appt_id}")
async def appts_delete(appt_id: int, user_id: int = Query(...)):
    async with POOL.acquire() as conn:
        r = await conn.execute("delete from app.appointments where id=$1 and user_id=$2", appt_id, user_id)
        if r.split()[-1] == "0":
            raise HTTPException(status_code=404, detail="appointment not found")
        return {"ok": True}
