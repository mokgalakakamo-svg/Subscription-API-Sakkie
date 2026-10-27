"""Public double opt-in email update subscription endpoints."""
import hashlib
import secrets

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from ..config import get_settings
from ..email_service import (
    EmailDeliveryError,
    send_subscribed_confirmation,
    send_subscription_confirmation,
)

router = APIRouter(prefix="/email-updates", tags=["email updates"])


def _db():
    from ..main import db
    if db is None:
        raise HTTPException(503, "Database is not initialized")
    return db


class EmailUpdateRequest(BaseModel):
    email: EmailStr


class EmailConfirmationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


@router.post("/subscriptions", status_code=status.HTTP_202_ACCEPTED)
async def subscribe_to_email_updates(body: EmailUpdateRequest):
    email = str(body.email).strip().lower()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    subscription = await _db().request_email_updates_subscription(email, token_hash)
    if subscription["status"] == "active":
        return {"message": "This email address is already subscribed to tender updates."}

    settings = get_settings()
    link = f"{settings.app_base_url}/email-updates/confirm?token={token}"
    try:
        await send_subscription_confirmation(email, link)
    except EmailDeliveryError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"message": "Check your inbox for a confirmation link to finish subscribing."}


@router.post("/confirm")
async def confirm_email_updates_subscription(body: EmailConfirmationRequest):
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    subscription = await _db().confirm_email_updates_subscription(token_hash)
    if not subscription:
        raise HTTPException(400, "Confirmation link is invalid or expired. Please subscribe again.")
    try:
        await send_subscribed_confirmation(subscription["email"])
    except EmailDeliveryError as exc:
        raise HTTPException(
            503,
            "Your subscription is confirmed, but we could not send the confirmation email. Please retry this link.",
        ) from exc
    await _db().finish_email_updates_confirmation(token_hash)
    return {"message": "Your email address is confirmed and you are subscribed to tender updates."}


