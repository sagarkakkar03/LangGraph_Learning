# HR Email Routing & RAG System: Testing & Deployment Guide

The core features of the application are now fully implemented. Because this system interacts with real email protocols (IMAP/SMTP) and filters out unauthorized users, **testing it requires specific setup**. 

If you sent an email and did not get a reply, please read the **Troubleshooting** section below carefully.

---

## Phase 1: Live Local Testing (Do This Now)

To see the system actually read emails, process them through LangGraph, and send replies, follow these steps:

### 1. Configure Your Test Email Account (The "HR Inbox")
1. Create a dedicated testing email account (e.g., a free Gmail account like `your-company-hr-test@gmail.com`).
2. Generate an **App Password** for this account (Standard passwords will not work for IMAP/SMTP).
   - *For Gmail: Go to Manage Account -> Security -> 2-Step Verification -> App Passwords.*
   - **Important:** Ensure IMAP is enabled in your Gmail settings (Settings -> Forwarding and POP/IMAP -> Enable IMAP).
3. Open your `.env` file and update the IMAP and SMTP sections with this email and App Password.
4. Set all the `EMAIL_*` variables (e.g., `EMAIL_MAIN`, `EMAIL_PAYROLL`) to this **same testing email address**. This allows you to see both the replies to the user AND the forwarded escalations in a single inbox without needing 9 different accounts.

### 2. Verify Your Connection
Run the connection test script to ensure your credentials are correct and IMAP/SMTP are reachable:
```bash
python test_email_connection.py
```
If this fails, do not proceed until it succeeds.

### 3. Whitelist Your Personal Email (CRITICAL STEP)
**You cannot send an email from `arjun.sharma@company.com` because you do not own that domain.** If you send an email from your personal Gmail, the system will look it up in the database, fail to find it, and silently ignore it.

To fix this:
1. Open `employee_data.csv`.
2. Find an employee (e.g., `EMP001, Arjun Sharma`) and change their email address to **your actual personal email address** (e.g., `sagar.personal@gmail.com`).
3. Open your terminal, drop the database, and re-seed it so your email is recognized:
   ```bash
   dropdb hr_system
   createdb hr_system
   python seed_db.py
   ```

### 4. Start the Mail Processor
The system only reads emails when the processor is running. Open a terminal and run:
```bash
python mail_processor.py
```
Leave this terminal open. It will poll the inbox every 30 seconds and print logs.

### 5. Execute Test Scenarios
Send the following emails from your **personal email** (the one you added to the CSV) to your **HR testing email account**. Watch the `mail_processor.py` terminal logs.

* **Test A (Standard RAG Answer):**
  * *Subject:* Leave Policy
  * *Body:* "Hi, I need to know what the parental leave policy is for my region."
  * *Expected:* The bot retrieves the policy, drafts a response, and replies to you. Check LangSmith for the trace!
* **Test B (Email Threading):**
  * *Action:* Reply directly to the bot's response from Test A with a follow-up question ("Does this apply to adopted children?").
  * *Expected:* The bot replies within the same email thread.
* **Test C (Attachment Auto-Escalation):**
  * *Subject:* Medical Certificate
  * *Body:* "Please find my sick leave certificate attached." (Attach a dummy PDF or image).
  * *Expected:* The bot detects the attachment and auto-escalates.

---

## Troubleshooting: "I sent an email but didn't get a reply"

Look at the terminal where `python mail_processor.py` is running. The logs will tell you exactly what went wrong.

**1. Log says: `Ignored: Sender not found in employee database.`**
* **Cause:** You sent the email from an address that is not in your Postgres database.
* **Fix:** Update `employee_data.csv` with the exact email address you are sending *from*, then run `dropdb hr_system && createdb hr_system && python seed_db.py`.

**2. Log says: `IMAP error: [AUTHENTICATIONFAILED]` or `SMTP error`**
* **Cause:** Your email provider rejected the login.
* **Fix:** Ensure you are using an **App Password**, not your normal email password. Ensure IMAP is enabled in your Gmail settings. Run `python test_email_connection.py` to verify.

**3. Log says: `Found 0 unread email(s).`**
* **Cause:** The email you sent was already marked as "Read" in the HR inbox, or it went to the Spam folder.
* **Fix:** Go into the HR test inbox, find your email, mark it as "Unread", and move it to the primary Inbox.

**4. Log says: `SMTP credentials not set — logging email instead of sending.`**
* **Cause:** Your `.env` file is missing the `SMTP_USER` or `SMTP_PASSWORD`.
* **Fix:** The system processed the email successfully but just printed the reply to the terminal instead of sending it. Add your SMTP credentials to `.env`.

**5. No Traces in LangSmith**
* **Cause:** The environment variables for LangSmith were previously incorrect or the workflow was never invoked.
* **Fix:** Ensure your `.env` has `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT`. (This has been fixed in the codebase, just ensure your `.env` is updated).

---

## Phase 2: Production Deployment & Hardening (Next Steps)

Once local testing is successful, proceed with these steps to move to production.

### 1. Infrastructure & Hosting
- **Database:** Migrate from local Postgres to a managed database (e.g., AWS RDS, Supabase, Neon).
- **Vector Store:** Currently, FAISS is stored locally on disk (`faiss_index/`). For a cloud deployment, migrate this to `pgvector` (inside your Postgres DB) or a managed vector DB like Pinecone so the index isn't lost when the server restarts.
- **Compute:** Deploy the FastAPI server (web service) and the Mail Processor (background worker) to a cloud provider like AWS ECS, Render, or Railway.

### 2. Document Management API
- Currently, updating HR documents requires a developer to run `python embed_documents.py`.
- **Action:** Add a `POST /documents/upload` endpoint in `main.py` that allows HR admins to upload new `.docx` files. The endpoint should automatically parse, chunk, embed, and update the database/vector store.