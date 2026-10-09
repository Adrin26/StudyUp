"""Outgoing email.

Only a console mailer exists for now: in development it prints messages to the
API log so password-reset links can be used without an email server. In
production nothing is printed; configure a real provider before enabling
self-service password recovery there.
"""

import logging

from ..config import get_settings

log = logging.getLogger("minda.mail")


def send(to: str, subject: str, body: str) -> bool:
    if get_settings().is_development:
        log.warning("DEV EMAIL to %s | %s\n%s", to, subject, body)
        return True
    log.error("No email provider configured; message to %s (%s) was not sent", to, subject)
    return False


def send_password_reset(to: str, name: str, link: str, ttl_minutes: int) -> bool:
    return send(
        to,
        "Reset your MINDA password",
        f"Hi {name},\n\nUse this link to choose a new password. It expires in {ttl_minutes} minutes and works once:\n{link}\n\n"
        "If you did not ask for this, you can ignore this email.",
    )
