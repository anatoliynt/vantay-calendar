from fastapi import FastAPI, Response, status, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import os
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator

app = FastAPI(title="vantay-fastapi")

# CORS: укажем разрешённые источники (добавите фронтовые домены по мере надобности)
ALLOWED_ORIGINS = [
    "https://cl.vantay.ru",
    "https://sub.vantay.ru",
    # "http://localhost:5173",  # раскомментируйте для локальной разработки
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ---------- USERS (как было) ----------
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

# ---------- CLIENTS ----------
class ClientCreate(BaseModel):
    user_id: int
    name: str = Field(min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

@app.get("/api/clients")
async def clients_list(user_id: int = Query(..., ge=1)):
    async with POOL.acquire() as conn:
        rows = await conn.fetch(
            "select id, user_id, name, email, phone, created_at, updated_at from app.clients where user_id=$1 order by id desc limit 100",
            user_id,
        )
        return {"items": [dict(r) for r in rows]}

@app.post("/api/clients")
async def clients_create(payload: ClientCreate, response: Response):
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            "insert into app.clients(user_id,name,email,phone) values($1,$2,$3,$4) "
            "returning id,user_id,name,email,phone,created_at,updated_at",
            payload.user_id, payload.name, payload.email, payload.phone
        )
        return {"ok": True, "item": dict(row)}

# ---------- APPOINTMENTS ----------
class AppointmentCreate(BaseModel):
    user_id: int
    client_id: Optional[int] = None
    start_at: datetime
    end_at: datetime
    title: Optional[str] = None
    notes: Optional[str] = None

    @validator("end_at")
    def check_time(cls, v, values):
        start = values.get("start_at")
        if start and v <= start:
            raise ValueError("end_at must be > start_at")
        return v

@app.get("/api/appointments")
async def appts_list(user_id: int = Query(..., ge=1)):
    async with POOL.acquire() as conn:
        rows = await conn.fetch(
            "select a.id,a.user_id,a.client_id,a.start_at,a.end_at,a.status,a.title,a.notes,"
            "a.created_at,a.updated_at, c.name as client_name "
            "from app.appointments a left join app.clients c on c.id=a.client_id "
            "where a.user_id=$1 order by a.start_at desc limit 100",
            user_id,
        )
        return {"items": [dict(r) for r in rows]}

@app.post("/api/appointments")
async def appts_create(payload: AppointmentCreate, response: Response):
    try:
        async with POOL.acquire() as conn:
            row = await conn.fetchrow(
                "insert into app.appointments(user_id,client_id,start_at,end_at,status,title,notes) "
                "values($1,$2,$3,$4,'scheduled',$5,$6) "
                "returning id,user_id,client_id,start_at,end_at,status,title,notes,created_at,updated_at",
                payload.user_id, payload.client_id, payload.start_at, payload.end_at, payload.title, payload.notes
            )
            return {"ok": True, "item": dict(row)}
    except Exception as e:
        # Например, сработает CONSTRAINT chk_appt_time
        response.status_code = 400
        return {"ok": False, "error": str(e)}
