import imaplib
import smtplib
import email as email_lib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from dataclasses import dataclass

from config import (
    IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    EMAIL_ADDRESSES,
)

logger = logging.getLogger(__name__)


@dataclass
class IncomingEmail:
    uid: str
    sender: str
    subject: str
    body: str
    message_id: str
    in_reply_to: str
    has_attachments: bool


# ------------------------------------------------------------------ #
#  IMAP — read unread emails from the hr@company.com inbox
# ------------------------------------------------------------------ #

def _decode_header_value(raw: str) -> str:
    parts = decode_header(raw or "")
    decoded = []
    for fragment, charset in parts:
        if isinstance(fragment, bytes):
            decoded.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(fragment)
    return "".join(decoded)


def _extract_body_and_attachments(msg: email_lib.message.Message) -> tuple[str, bool]:
    body = ""
    has_attachments = False
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if disposition and "attachment" in disposition.lower():
                has_attachments = True
            elif content_type == "text/plain" and "attachment" not in disposition.lower():
                payload = part.get_payload(decode=True)
                if payload and not body:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body, has_attachments


def _extract_sender_email(from_header: str) -> str:
    """Pull just the email address from 'Name <email>' format."""
    if "<" in from_header and ">" in from_header:
        return from_header.split("<")[1].split(">")[0].strip()
    return from_header.strip()


def fetch_unread_emails() -> list[IncomingEmail]:
    """Connect to IMAP, fetch all UNSEEN emails, mark them as SEEN, return them."""
    if not IMAP_USER or not IMAP_PASSWORD:
        logger.warning("IMAP credentials not set — skipping inbox check.")
        return []

    emails: list[IncomingEmail] = []
    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        conn.login(IMAP_USER, IMAP_PASSWORD)
        conn.select("INBOX")

        status, data = conn.uid("search", None, "UNSEEN")
        if status != "OK" or not data[0]:
            conn.logout()
            return []

        uids = data[0].split()
        logger.info("Found %d unread email(s).", len(uids))

        for uid in uids:
            uid_str = uid.decode()
            status, msg_data = conn.uid("fetch", uid, "(RFC822)")
            if status != "OK":
                continue

            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            from_raw = _decode_header_value(msg.get("From", ""))
            subject = _decode_header_value(msg.get("Subject", ""))
            message_id = _decode_header_value(msg.get("Message-ID", ""))
            in_reply_to = _decode_header_value(msg.get("In-Reply-To", ""))
            body, has_attachments = _extract_body_and_attachments(msg)
            sender = _extract_sender_email(from_raw)

            emails.append(IncomingEmail(
                uid=uid_str,
                sender=sender,
                subject=subject,
                body=body.strip(),
                message_id=message_id,
                in_reply_to=in_reply_to,
                has_attachments=has_attachments,
            ))

            conn.uid("store", uid, "+FLAGS", "(\\Seen)")

        conn.logout()
    except Exception as exc:
        logger.error("IMAP error: %s", exc)

    return emails


# ------------------------------------------------------------------ #
#  SMTP — send emails
# ------------------------------------------------------------------ #

def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    extra_headers: dict | None = None,
) -> dict:
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
    
    if extra_headers:
        for k, v in extra_headers.items():
            if v:
                msg[k] = v
                
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


def forward_to_department(
    department: str,
    sender_email: str,
    query: str,
    response_body: str,
    subject: str = "",
    message_id: str = "",
) -> dict:
    """Forward the original query to the department and reply to the sender."""
    dept_email = EMAIL_ADDRESSES.get(department)
    if not dept_email:
        return {"success": False, "message": f"Unknown department: {department}"}

    fwd_subject = f"[HR Router] {subject or 'New query'} from {sender_email}"
    fwd_result = send_email(
        to_email=dept_email,
        subject=fwd_subject,
        body=f"Original query from {sender_email}:\n\n{query}",
    )

    reply_headers = {}
    if message_id:
        reply_headers["In-Reply-To"] = message_id
        reply_headers["References"] = message_id

    reply_result = send_email(
        to_email=sender_email,
        subject=f"RE: {subject or 'Your HR query'}",
        body=response_body,
        from_email=dept_email,
        extra_headers=reply_headers,
    )

    return {
        "forward": fwd_result,
        "reply": reply_result,
    }
