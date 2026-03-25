import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import imaplib
from app.core.config import IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD
try:
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(IMAP_USER, IMAP_PASSWORD)
    conn.select("INBOX")
    conn.uid("store", "21", "-FLAGS", "(\\Seen)")
    print("Marked UID 21 as UNSEEN.")
    conn.logout()
except Exception as e:
    print(f"Error: {e}")
