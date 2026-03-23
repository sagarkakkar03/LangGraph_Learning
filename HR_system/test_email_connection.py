import imaplib
import smtplib
from config import (
    IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
)

def test_imap():
    print(f"Testing IMAP connection to {IMAP_HOST}:{IMAP_PORT} as {IMAP_USER}...")
    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        conn.login(IMAP_USER, IMAP_PASSWORD)
        status, data = conn.select("INBOX")
        print(f"✅ IMAP Login Successful! INBOX has {data[0].decode()} emails.")
        
        status, data = conn.uid("search", None, "UNSEEN")
        unread_count = len(data[0].split()) if data[0] else 0
        print(f"✅ Found {unread_count} UNREAD emails.")
        conn.logout()
    except Exception as e:
        print(f"❌ IMAP Error: {e}")

def test_smtp():
    print(f"\nTesting SMTP connection to {SMTP_HOST}:{SMTP_PORT} as {SMTP_USER}...")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            print("✅ SMTP Login Successful!")
    except Exception as e:
        print(f"❌ SMTP Error: {e}")

if __name__ == "__main__":
    test_imap()
    test_smtp()
