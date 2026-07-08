"""Support ticket endpoint — sends email via SMTP2GO (port 25, no auth)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])

SMTP_HOST = "mail.smtp2go.com"
SMTP_PORT = 25
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@haley365.com")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@haley365.com")


class TicketRequest(BaseModel):
    email: EmailStr
    message: str


@router.post("/ticket")
def create_ticket(body: TicketRequest, user: dict = Depends(get_current_user)) -> dict:
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    customer_id: str = user.get("customer_id", "")
    customer_name: str = user.get("name", "") or user.get("email", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Support Request from {customer_name or customer_id} ({body.email})"
    msg["From"] = body.email
    msg["To"] = SUPPORT_EMAIL

    text_body = (
        f"Customer: {customer_name} ({customer_id})\n"
        f"Email: {body.email}\n\n"
        f"Message:\n{body.message}"
    )
    html_body = (
        f"<p><strong>Customer:</strong> {customer_name} ({customer_id})<br>"
        f"<strong>Email:</strong> {body.email}</p>"
        f"<p><strong>Message:</strong><br>{body.message.replace(chr(10), '<br>')}</p>"
    )

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.sendmail(SENDER_EMAIL, SUPPORT_EMAIL, msg.as_string())
    except Exception as exc:
        logger.error("SMTP send failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to send email — please try again later")

    return {"ok": True}
