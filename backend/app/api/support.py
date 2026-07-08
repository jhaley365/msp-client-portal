"""Support ticket endpoint — sends an email via AWS SES."""

from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.config import DYNAMODB_REGION
from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])

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

    subject = f"Support Request from {customer_name or customer_id} ({body.email})"
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

    try:
        ses = boto3.client("ses", region_name=DYNAMODB_REGION)
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [SUPPORT_EMAIL]},
            ReplyToAddresses=[body.email],
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
    except ClientError as exc:
        logger.error("SES send_email failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to send email — please try again later")

    return {"ok": True}
