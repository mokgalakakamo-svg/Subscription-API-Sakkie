"""Customer accounts and subscription endpoints for the Client API."""
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from ..config import get_settings

router = APIRouter(tags=["subscriptions"])
settings = get_settings()


def _db():
    from ..main import db
    if db is None:
        raise HTTPException(503, "Database is not initialized")
    return db


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _token_for(customer: dict) -> str:
    if not settings.jwt_secret_key:
        raise HTTPException(503, "JWT_SECRET_KEY is not configured")
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "sub": str(customer["id"]), "email": customer["email"],
        "iss": settings.jwt_issuer, "iat": now,
        "exp": now + settings.jwt_access_token_minutes * 60,
    }, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}"
    signature = _b64(hmac.new(settings.jwt_secret_key.encode(), signing_input.encode(), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


async def current_customer(authorization: str | None = Header(default=None)):
    if not settings.jwt_secret_key:
        raise HTTPException(503, "JWT_SECRET_KEY is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer access token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        token = authorization[7:].strip()
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}"
        expected = _b64(hmac.new(settings.jwt_secret_key.encode(), signing_input.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if claims.get("iss") != settings.jwt_issuer or int(claims["exp"]) <= int(time.time()):
            raise ValueError("expired or invalid token")
        customer_id = int(claims["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    customer = await _db().get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(401, "Customer account no longer exists")
    return customer


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SubscriptionRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=40)


@router.get("/plans")
async def list_plans():
    plans = await _db().list_subscription_plans()
    for plan in plans:
        plan["amount"] = plan["amount_minor"] / 100
    return {"plans": plans}


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(body: Credentials):
    if not settings.jwt_secret_key:
        raise HTTPException(503, "JWT_SECRET_KEY is not configured")
    email = str(body.email).strip().lower()
    try:
        customer = await _db().create_customer(email, _password_hash(body.password))
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "An account with this email already exists")
    return {"customer": customer, "access_token": _token_for(customer), "token_type": "bearer", "expires_in": settings.jwt_access_token_minutes * 60}


@router.post("/auth/login")
async def login(body: LoginCredentials):
    if not settings.jwt_secret_key:
        raise HTTPException(503, "JWT_SECRET_KEY is not configured")
    customer = await _db().get_customer_by_email(str(body.email).strip().lower())
    if not customer or not _verify_password(body.password, customer["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    customer.pop("password_hash", None)
    return {"customer": customer, "access_token": _token_for(customer), "token_type": "bearer", "expires_in": settings.jwt_access_token_minutes * 60}


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
async def start_subscription(body: SubscriptionRequest, customer=Depends(current_customer)):
    db = _db()
    plan = await db.get_subscription_plan(body.plan_code)
    if not plan:
        raise HTTPException(404, "Active subscription plan not found")
    if plan["amount_minor"] > 0 and settings.billing_mode != "mock":
        raise HTTPException(503, "Paid billing is not configured; choose the free plan or configure a payment provider")
    reference = f"mock_{uuid.uuid4().hex}" if settings.billing_mode == "mock" else f"free_{uuid.uuid4().hex}"
    try:
        subscription = await db.create_subscription(customer["id"], body.plan_code, reference)
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "An active or pending subscription already exists")
    if not subscription:
        raise HTTPException(404, "Active subscription plan not found")
    if plan["amount_minor"] == 0:
        subscription = await db.activate_mock_subscription(subscription["id"], customer["id"])
        return {"subscription": subscription, "payment_required": False}
    return {"subscription": subscription, "payment_required": True, "message": "Mock billing is enabled. Confirm via POST /subscriptions/{id}/mock-confirm."}


@router.get("/subscriptions/me")
async def my_subscription(customer=Depends(current_customer)):
    subscription = await _db().get_current_subscription(customer["id"])
    return {"subscription": subscription}


@router.post("/subscriptions/{subscription_id}/mock-confirm")
async def mock_confirm(subscription_id: int, customer=Depends(current_customer)):
    if settings.billing_mode != "mock":
        raise HTTPException(404, "Not found")
    subscription = await _db().activate_mock_subscription(subscription_id, customer["id"])
    if not subscription:
        raise HTTPException(404, "Pending subscription not found")
    return {"subscription": subscription}


@router.post("/subscriptions/me/cancel")
async def cancel_subscription(customer=Depends(current_customer)):
    subscription = await _db().cancel_subscription(customer["id"])
    if not subscription:
        raise HTTPException(404, "No pending or active subscription found")
    return {"subscription": subscription}
