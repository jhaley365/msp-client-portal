"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.inventory import router as inventory_router
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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
