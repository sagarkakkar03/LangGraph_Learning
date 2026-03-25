"""
Mail Processor — continuously polls the hr@company.com inbox and routes
each incoming email through the LangGraph workflow.

Usage:
    python mail_processor.py
"""

import time
import logging

from app.core.config import POLL_INTERVAL_SECONDS, EMAIL_ADDRESSES
from app.db.database import init_db
from app.services.email_service import fetch_unread_emails, IncomingEmail
from app.agents.graph import workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("mail_processor")


def process_email(mail: IncomingEmail) -> dict:
    """Run a single email through the LangGraph workflow."""
    query = mail.body
    if mail.subject:
        query = f"Subject: {mail.subject}\n\n{mail.body}"

    result = workflow.invoke({
        "query": query,
        "subject": mail.subject,
        "sender_email": mail.sender,
        "message_id": mail.message_id,
        "in_reply_to": mail.in_reply_to,
        "has_attachments": mail.has_attachments,
    })
    return result


def poll_once() -> int:
    """Fetch unread emails and process each one. Returns count processed."""
    emails = fetch_unread_emails()
    if not emails:
        return 0

    for mail in emails:
        logger.info(
            "Processing email uid=%s from=%s subject='%s'",
            mail.uid, mail.sender, mail.subject,
        )
        try:
            result = process_email(mail)
            logger.info(
                "  -> Routed to %s (%s). Reasoning: %s",
                result.get("department"),
                result.get("target_email"),
                result.get("reasoning"),
            )
            status = result.get("email_status", {})
            fwd = status.get("forward", {})
            reply = status.get("reply", {})
            logger.info(
                "  -> Forward: %s | Reply: %s",
                fwd.get("message", "n/a"),
                reply.get("message", "n/a"),
            )
        except Exception:
            logger.exception("  -> Failed to process email uid=%s", mail.uid)

    return len(emails)


def run():
    init_db()
    main_email = EMAIL_ADDRESSES["main"]
    interval = POLL_INTERVAL_SECONDS

    logger.info("Mail processor started.")
    logger.info("  Inbox   : %s", main_email)
    logger.info("  Polling : every %ds", interval)
    logger.info("  Departments: %s", ", ".join(
        f"{k}={v}" for k, v in EMAIL_ADDRESSES.items() if k != "main"
    ))

    while True:
        try:
            count = poll_once()
            if count:
                logger.info("Processed %d email(s) this cycle.", count)
        except Exception:
            logger.exception("Error during poll cycle.")

        time.sleep(interval)


if __name__ == "__main__":
    run()
