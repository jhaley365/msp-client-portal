"""Authentication endpoints: login and token refresh."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.security import create_access_token
from app.services.customer_service import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer_id: str
    name: str
    is_admin: bool = False


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    customer = authenticate(body.email, body.password)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
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
