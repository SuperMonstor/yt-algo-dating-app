"""
YT Algo Dating App — FastAPI server.

Run with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_pool, close_pool
from app.routes import health, upload, status, profile, fingerprint, matches, user


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

# Public routes
app.include_router(health.router)

# Authenticated routes
app.include_router(upload.router)
app.include_router(status.router)
app.include_router(profile.router)
app.include_router(fingerprint.router)
app.include_router(matches.router)
app.include_router(user.router)
