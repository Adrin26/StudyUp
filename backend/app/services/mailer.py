"""Outgoing email.

With SMTP_HOST set, messages go through that SMTP server. Without it,
development prints messages to the API log so password-reset links can be used
without an email server, and production sends nothing (callers report that the
link could not be emailed). Message bodies contain single-use links, so they
are never logged outside development.
"""

import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger("minda.mail")


def _smtp_send(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Email to %s (%s) failed: %s", to, subject, type(exc).__name__)
        return False


def send(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if s.smtp_host:
        return _smtp_send(to, subject, body)
    if s.is_development:
        log.warning("DEV EMAIL to %s | %s\n%s", to, subject, body)
        return True
    log.error("No email provider configured; message to %s (%s) was not sent", to, subject)
    return False


def send_invitation(to: str, name: str, school: str | None, link: str, ttl_hours: int) -> bool:
    return send(
        to,
        "Your MINDA account is ready",
        f"Hi {name},\n\n{school or 'Your school'} has created a MINDA account for you. "
        f"Use this link to choose your password. It expires in {ttl_hours} hours and works once:\n{link}\n\n"
        "If you were not expecting this, contact your school office.",
    )


def send_password_reset(to: str, name: str, link: str, ttl_minutes: int) -> bool:
    return send(
        to,
        "Reset your MINDA password",
        f"Hi {name},\n\nUse this link to choose a new password. It expires in {ttl_minutes} minutes and works once:\n{link}\n\n"
        "If you did not ask for this, you can ignore this email.",
    )
