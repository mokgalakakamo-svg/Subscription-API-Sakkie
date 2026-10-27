"""SMTP delivery for email update subscription messages."""
import asyncio
import ssl
import smtplib
from email.message import EmailMessage

from .config import get_settings


class EmailDeliveryError(Exception):
    pass


def _send_message(recipient: str, subject: str, text: str, html: str):
    settings = get_settings()
    if not settings.smtp_host:
        raise EmailDeliveryError("SMTP_HOST is not configured")
    sender = settings.smtp_from_email or settings.smtp_username
    if not sender:
        raise EmailDeliveryError("SMTP_FROM_EMAIL is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Email delivery failed") from exc


async def send_email(recipient: str, subject: str, text: str, html: str):
    await asyncio.to_thread(_send_message, recipient, subject, text, html)


async def send_subscription_confirmation(recipient: str, link: str):
    await send_email(
        recipient,
        "Confirm your tender updates subscription",
        f"Confirm your email address to subscribe to tender updates: {link}\n\n"
        "This link expires in 24 hours. If you did not request this, ignore this email.",
        f"<p>Confirm your email address to subscribe to tender updates.</p>"
        f"<p><a href=\"{link}\">Confirm my email address</a></p>"
        "<p>This link expires in 24 hours. If you did not request this, ignore this email.</p>",
    )


async def send_subscribed_confirmation(recipient: str):
    await send_email(
        recipient,
        "You are subscribed to tender updates",
        "Your email address has been confirmed. You are now subscribed to tender updates.",
        "<p>Your email address has been confirmed.</p>"
        "<p>You are now subscribed to tender updates.</p>",
    )
