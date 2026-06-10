"""Mailjet email alert service."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_alert(
    mj_api_key: str,
    mj_api_secret: str,
    from_email: str,
    to_email: str,
    subject: str,
    text_body: str,
) -> bool:
    """Send an email via Mailjet. Returns True on success."""
    try:
        from mailjet_rest import Client  # type: ignore

        mj = Client(auth=(mj_api_key, mj_api_secret), version="v3.1")
        data = {
            "Messages": [
                {
                    "From": {"Email": from_email, "Name": "DDNS Manager"},
                    "To": [{"Email": to_email}],
                    "Subject": subject,
                    "TextPart": text_body,
                }
            ]
        }
        result = mj.send.create(data=data)
        if result.status_code == 200:
            logger.info("Alert email sent to %s: %s", to_email, subject)
            return True
        logger.error("Mailjet error %s: %s", result.status_code, result.json())
        return False
    except Exception as exc:
        logger.error("Failed to send alert email: %s", exc)
        return False


def maybe_send(
    settings,
    subject: str,
    body: str,
) -> None:
    """Send only if Mailjet credentials are configured."""
    if not all([
        settings.mj_api_key,
        settings.mj_api_secret,
        settings.alert_from_email,
        settings.alert_to_email,
    ]):
        logger.debug("Email alerts not configured, skipping.")
        return
    send_alert(
        mj_api_key=settings.mj_api_key,
        mj_api_secret=settings.mj_api_secret,
        from_email=settings.alert_from_email,
        to_email=settings.alert_to_email,
        subject=subject,
        text_body=body,
    )
