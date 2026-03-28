"""
YT Algo Dating App — FastAPI server.

Run with:
    uvicorn app.main:app --reload
"""

from uuid import UUID, uuid4
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_pool, close_pool
from app.auth import get_current_user
from app.routes import health, upload, status, profile, fingerprint, matches, user

# Dev mode: named test users (hardcoded so they survive server restarts)
DEV_USERS = {
    "dhruv": UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    "nauman": UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff"),
    "tarun": UUID("cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"),
    "chaitanya": UUID("dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb"),
    "deekshith": UUID("eeeeeeee-ffff-aaaa-bbbb-cccccccccccc"),
    "srusti": UUID("ffffffff-aaaa-bbbb-cccc-dddddddddddd"),
    "samuditha": UUID("11111111-2222-3333-4444-555555555555"),
    "rachita": UUID("22222222-3333-4444-5555-666666666666"),
}
_current_dev_user = "dhruv"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(
    title="YT Algo Dating App",
    description="Match people based on YouTube long-form consumption patterns",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dev mode: bypass auth, switch user via X-Dev-User header
def _dev_user():
    return DEV_USERS.get(_current_dev_user, list(DEV_USERS.values())[0])

app.dependency_overrides[get_current_user] = _dev_user


@app.get("/dev/switch/{name}")
async def switch_dev_user(name: str):
    """Dev only: switch between named test users."""
    global _current_dev_user
    if name not in DEV_USERS:
        return {"error": "Unknown user", "available": list(DEV_USERS.keys())}
    _current_dev_user = name
    return {"switched_to": name, "user_id": str(DEV_USERS[name])}


@app.post("/dev/add/{name}")
async def add_dev_user(name: str):
    """Dev only: add a new named test user."""
    if name in DEV_USERS:
        return {"exists": name, "user_id": str(DEV_USERS[name])}
    DEV_USERS[name] = uuid4()
    return {"added": name, "user_id": str(DEV_USERS[name])}


@app.get("/dev/users")
async def list_dev_users():
    """Dev only: list all named test users."""
    return {
        "current": _current_dev_user,
        "users": {name: str(uid) for name, uid in DEV_USERS.items()},
    }


# Public routes
app.include_router(health.router)

# Authenticated routes
app.include_router(upload.router)
app.include_router(status.router)
app.include_router(profile.router)
app.include_router(fingerprint.router)
app.include_router(matches.router)
app.include_router(user.router)
