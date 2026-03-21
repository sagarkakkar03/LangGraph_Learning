import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_ADDRESSES

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
) -> dict:
    """Send an email via SMTP.

    Returns a dict with 'success' (bool) and 'message' (str).
    If SMTP credentials are not configured, logs the email instead of sending.
    """
    from_email = from_email or EMAIL_ADDRESSES["main"]

    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning(
            "SMTP credentials not set — logging email instead of sending.\n"
            "  From: %s\n  To: %s\n  Subject: %s",
            from_email, to_email, subject,
        )
        return {
            "success": True,
            "message": "SMTP not configured — email logged locally.",
        }

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(from_email, to_email, msg.as_string())
        logger.info("Email sent to %s", to_email)
        return {"success": True, "message": f"Email sent to {to_email}"}
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return {"success": False, "message": str(exc)}


def forward_to_department(department: str, sender_email: str, query: str, response_body: str) -> dict:
    """Forward the query to the department email and send the response back to the sender."""
    dept_email = EMAIL_ADDRESSES.get(department)
    if not dept_email:
        return {"success": False, "message": f"Unknown department: {department}"}

    fwd_result = send_email(
        to_email=dept_email,
        subject=f"[HR Router] New query from {sender_email}",
        body=f"Original query from {sender_email}:\n\n{query}",
    )

    reply_result = send_email(
        to_email=sender_email,
        subject="RE: Your HR query",
        body=response_body,
        from_email=dept_email,
    )

    return {
        "forward": fwd_result,
        "reply": reply_result,
    }
