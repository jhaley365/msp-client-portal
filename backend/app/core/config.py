"""Central configuration loaded from environment variables."""

from __future__ import annotations

import os

# JWT
JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))  # 8 hours

# DynamoDB
DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
DYNAMODB_ENDPOINT_URL: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

# CORS — set to your domain in production
CORS_ORIGINS: list[str] = os.environ.get("CORS_ORIGINS", "*").split(",")

# RDS SQL Server (XGuardian)
RDS_HOST: str = os.environ.get("RDS_HOST", "")
RDS_USER: str = os.environ.get("RDS_USER", "")
RDS_PASSWORD: str = os.environ.get("RDS_PASSWORD", "")
RDS_DATABASE: str = os.environ.get("RDS_DATABASE", "xguardian_15")
