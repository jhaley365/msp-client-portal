"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.huntress import router as huntress_router
from app.api.inventory import router as inventory_router
from app.api.o365 import router as o365_router
from app.api.scoutdns import router as scoutdns_router
from app.api.syncro import router as syncro_router
from app.core.config import CORS_ORIGINS

app = FastAPI(title="MSP Client Portal API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(syncro_router, prefix="/api")
app.include_router(huntress_router, prefix="/api")
app.include_router(scoutdns_router, prefix="/api")
app.include_router(o365_router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
