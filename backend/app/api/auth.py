"""Authentication endpoints: password login + magic link (passwordless)."""

from __future__ import annotations

import logging
import os
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from fastapi import APIRouter, HTTPException, Request, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from app.core.config import JWT_ALGORITHM, JWT_SECRET_KEY
from app.core.security import create_access_token
from app.services.customer_service import authenticate
from app.services.user_service import get_user_by_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

SMTP_HOST = "mail.smtp2go.com"
SMTP_PORT = 25
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@haley365.com")
PORTAL_URL = os.environ.get("PORTAL_URL", "https://portal.haley365.com")
MAGIC_EXPIRE_MINUTES = 15


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _record_login(user: dict, ip: str) -> None:
    try:
        kwargs: dict = {"region_name": DYNAMODB_REGION}
        if _ENDPOINT:
            kwargs["endpoint_url"] = _ENDPOINT
        tbl = boto3.resource("dynamodb", **kwargs).Table("LoginAudit")
        tbl.put_item(Item={
            "login_id": str(uuid.uuid4()),
            "customer_id": user["customer_id"],
            "user_id": user.get("user_id", ""),
            "email": user["email"],
            "name": user.get("name", ""),
            "ip_address": ip,
            "logged_in_at": datetime.now(tz=timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.error("Failed to write login audit record: %s", exc)


# ---------------------------------------------------------------------------
# Shared response model
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer_id: str
    name: str
    email: str = ""
    is_admin: bool = False


# ---------------------------------------------------------------------------
# Password login (legacy — kept for existing admin accounts in Customers table)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    customer = authenticate(body.email, body.password)
    if not customer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid email or password")
    is_admin = bool(customer.get("is_admin", False))
    token = create_access_token({
        "sub": customer["customer_id"],
        "email": customer["email"],
        "name": customer.get("name", ""),
        "is_admin": is_admin,
    })
    return TokenResponse(
        access_token=token,
        customer_id=customer["customer_id"],
        name=customer.get("name", ""),
        is_admin=is_admin,
    )


# ---------------------------------------------------------------------------
# Magic link — request
# ---------------------------------------------------------------------------

class MagicLinkRequest(BaseModel):
    email: EmailStr


@router.post("/magic-link")
def request_magic_link(body: MagicLinkRequest, request: Request) -> dict:
    """Send a one-time login link to the given email address."""
    email = body.email.lower().strip()
    user = get_user_by_email(email)

    # Always return the same response — don't leak whether email exists.
    if not user or not user.get("is_active"):
        logger.info("Magic link requested for unknown/inactive email: %s", email)
        return {"sent": True}

    magic_payload = {
        "type": "magic",
        "sub": user["user_id"],
        "email": email,
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=MAGIC_EXPIRE_MINUTES),
    }
    token = jwt.encode(magic_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    # Build the verify URL from the portal's configured base URL.
    verify_url = f"{PORTAL_URL}/auth/verify?token={token}"
    name = user.get("name") or email

    subject = "Your Haley365 Portal login link"
    text_body = (
        f"Hi {name},\n\n"
        f"Click the link below to sign in to the Haley365 Client Portal.\n"
        f"This link expires in {MAGIC_EXPIRE_MINUTES} minutes.\n\n"
        f"{verify_url}\n\n"
        f"If you did not request this link, you can safely ignore this email.\n\n"
        f"— Haley365"
    )
    html_body = f"""
<div style="font-family:'IBM Plex Sans',system-ui,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;background:#0c111e;color:#eaf0fb;border-radius:12px">
  <div style="font-size:13px;font-weight:800;letter-spacing:0.14em;color:#fff;margin-bottom:4px">HALEY365</div>
  <div style="font-size:9px;letter-spacing:0.22em;color:#7f8ea3;margin-bottom:28px">CLIENT PORTAL</div>
  <p style="color:#eaf0fb;font-size:15px;margin:0 0 8px">Hi {name},</p>
  <p style="color:#8a97ab;font-size:13px;margin:0 0 24px">
    Click the button below to sign in to the Haley365 Client Portal.<br>
    This link expires in <strong style="color:#eaf0fb">{MAGIC_EXPIRE_MINUTES} minutes</strong>.
  </p>
  <a href="{verify_url}"
     style="display:inline-block;background:#2f6bff;color:#fff;font-size:13px;font-weight:600;
            padding:12px 28px;border-radius:9px;text-decoration:none;letter-spacing:0.01em">
    Sign in to Portal
  </a>
  <p style="color:#7f8ea3;font-size:11.5px;margin:24px 0 0">
    If you did not request this link you can safely ignore this email.
  </p>
</div>
"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = email
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.sendmail(SENDER_EMAIL, email, msg.as_string())
        logger.info("Magic link sent to %s", email)
    except Exception as exc:
        logger.error("Failed to send magic link to %s: %s", email, exc)
        raise HTTPException(status_code=502, detail="Failed to send login email — please try again")

    return {"sent": True}


# ---------------------------------------------------------------------------
# Magic link — verify
# ---------------------------------------------------------------------------

class MagicVerifyRequest(BaseModel):
    token: str


@router.post("/magic-link/verify", response_model=TokenResponse)
def verify_magic_link(body: MagicVerifyRequest, request: Request) -> TokenResponse:
    """Exchange a magic token for a full session JWT."""
    exc_invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login link is invalid or has expired. Please request a new one.",
    )
    try:
        payload = jwt.decode(body.token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise exc_invalid

    if payload.get("type") != "magic":
        raise exc_invalid

    user_id: str = payload.get("sub", "")
    user = get_user_by_email(payload.get("email", ""))
    if not user or not user.get("is_active") or user.get("user_id") != user_id:
        raise exc_invalid

    is_admin = bool(user.get("is_admin", False))
    session_token = create_access_token({
        "sub": user["customer_id"],
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "is_admin": is_admin,
    })
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    _record_login(user, ip)
    return TokenResponse(
        access_token=session_token,
        customer_id=user["customer_id"],
        name=user.get("name", ""),
        email=user["email"],
        is_admin=is_admin,
    )
