# HR Email Routing & RAG System: Testing & Deployment Guide

Three issues have been fixed in this update. Follow the steps below in exact order to apply the fixes and verify everything works.

---

## What Was Fixed

### Fix 1: Wrong Reply Email Address (e.g. +benefits instead of +peopleteam)

**Root cause:** The LLM classifier routes "leave policy" queries to `benefits` because the benefits department keywords included "PTO, leave policy". But the HR documents say leave policies belong to `people_operations` (People Team).

**What changed:**
- `config.py` — Moved "leave policy, parental leave, sick leave, vacation, PTO" from `benefits` keywords to `people_team` keywords.
- `config.py` — Added `DOC_ESCALATION_TO_DEPT` mapping that translates document-level department names (e.g. `people_operations`) to our routing keys (e.g. `people_team`).
- `graph.py` — After the RAG agent retrieves documents, the `rag_lookup` node now reads the `escalation_department` metadata from the retrieved chunks and **overrides** the classifier's department pick. So even if the classifier says `benefits`, the documents win and routing goes to `people_team`.

### Fix 2: RAG Not Finding the Right Country's Documents

**Root cause (already partially fixed):** The `analyze_query` node in `rag_agent.py` extracts the target country from the query. If an Argentine employee asks about Brazil's policy, `target_country` is set to `Brazil` and the FAISS search filters to `country=Brazil`. This was added in the previous update.

**If this is still not working** for you, it means you need to **rebuild the FAISS index** because the old index doesn't have proper country metadata. See Step 4 below.

### Fix 3: LangSmith Observability Not Working

**Root cause:** The `.env` file uses `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`, but LangChain/LangGraph only reads env vars prefixed with `LANGCHAIN_*`.

**What changed:**
- `config.py` — Now reads both naming conventions (`LANGCHAIN_*` and `LANGSMITH_*`) and always sets the correct `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT` env vars at startup. Your existing `.env` will work without changes.

---

## Step-by-Step: Apply the Fixes and Test

### Step 1: Update Your `.env` File (Optional but Recommended)

Your `.env` file works as-is because `config.py` now reads both naming conventions. But for clarity, you can update the LangSmith section to use the canonical names:

```
# LangSmith Observability (canonical names)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=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
LANGCHAIN_PROJECT=LangMail
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

This is optional — the old `LANGSMITH_*` names will still work after the code fix.

### Step 2: Make Sure Postgres Is Running

```bash
pg_isready
```

Expected output: `localhost:5432 - accepting connections`

If not running, start it:
```bash
# macOS with Homebrew
brew services start postgresql@15

# Or whatever version you have
brew services start postgresql
```

### Step 3: Re-Seed the Database

If you already seeded once, you should re-seed to ensure the data is fresh:

```bash
cd /Users/sagar/Desktop/coding/LangGraph_Practice/HR_system
python seed_db.py
```

This seeds both employees and HR document metadata. It will not destroy existing data — it checks before inserting.

### Step 4: Rebuild the FAISS Index (CRITICAL)

The FAISS index stores the metadata used for country filtering and department routing. If your old index was built before the `analyze_query` and escalation fixes, you **must** rebuild it:

```bash
cd /Users/sagar/Desktop/coding/LangGraph_Practice/HR_system
python embed_documents.py
```

Expected output:
```
Found X active HR documents in DB.
Processed X docs, skipped Y, total Z chunks.
Building FAISS index with Z chunks...
FAISS index saved to /Users/sagar/Desktop/coding/LangGraph_Practice/HR_system/faiss_index
```

**Verify country metadata is correct:**

Open a Python shell and run:
```python
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from config import EMBEDDING_MODEL, FAISS_INDEX_DIR

vs = FAISS.load_local(FAISS_INDEX_DIR, OpenAIEmbeddings(model=EMBEDDING_MODEL), allow_dangerous_deserialization=True)
results = vs.similarity_search("parental leave", k=5, fetch_k=400, filter={"country": "Brazil"})
for doc in results:
    print(doc.metadata.get("doc_code"), doc.metadata.get("country"), doc.metadata.get("escalation_department"))
```

**Expected:** You should see results with `country=Brazil` and doc codes starting with `BR-HR-*`. If you see `None` or `Argentina` results, the index is stale — delete `faiss_index/` and re-run `python embed_documents.py`.

### Step 5: Verify the Email Connection

```bash
cd /Users/sagar/Desktop/coding/LangGraph_Practice/HR_system
python test_email_connection.py
```

Both IMAP and SMTP should show `OK`.

### Step 6: Start the Mail Processor

```bash
cd /Users/sagar/Desktop/coding/LangGraph_Practice/HR_system
python mail_processor.py
```

Leave this terminal open. You should see:
```
Starting HR mail processor...
IMAP: hrcompanyexample@gmail.com @ imap.gmail.com:993
Poll interval: 30s
--- Polling inbox ---
Found 0 unread email(s).
```

### Step 7: Run the Test Scenarios

Send the following emails **from the email address that is in your employee database** (the one mapped to an Argentine employee) to `hrcompanyexample@gmail.com`.

#### Test A: Cross-Country RAG Query (Main Fix)

- **Subject:** `Parental Leave in Brazil`
- **Body:** `Hi, can you tell me what the parental leave policy is for employees based in Brazil?`
- **Expected result:**
  1. The `analyze_query` node extracts `target_country = Brazil` from the query text (even though the sender is from Argentina).
  2. The `retrieve` node filters FAISS to `country=Brazil`.
  3. The `generate_answer` node writes a response citing Brazilian policy documents (`BR-HR-*`).
  4. The reply email arrives from `kakkarsagar03+peopleteam@gmail.com` (People Team), NOT from `+benefits`.
  5. LangSmith shows the full trace under the `LangMail` project.

#### Test B: Same-Country RAG Query (Baseline)

- **Subject:** `Leave Policy`
- **Body:** `What is the parental leave policy for me?`
- **Expected result:**
  1. The `analyze_query` node sees no explicit country → falls back to `sender_country = Argentina`.
  2. The response cites Argentine policy documents (`AR-HR-*`).
  3. The reply comes from `kakkarsagar03+peopleteam@gmail.com`.

#### Test C: Email Address Verification

- **Subject:** `Payroll Question`
- **Body:** `When is the next pay date and how do I read my payslip?`
- **Expected result:**
  1. Classified to `payroll` department.
  2. Reply comes from `kakkarsagar03+payroll@gmail.com`.

#### Test D: Attachment Auto-Escalation

- **Subject:** `Medical Certificate`
- **Body:** `Please find my sick leave certificate attached.`
- **Attach:** Any small PDF or image file.
- **Expected result:**
  1. The system detects the attachment.
  2. The query is auto-escalated with reason "Email contains attachments that require human review."

### Step 8: Verify LangSmith Traces

1. Go to [https://smith.langchain.com](https://smith.langchain.com).
2. Select the project `LangMail` (or whatever your `LANGCHAIN_PROJECT` / `LANGSMITH_PROJECT` is set to).
3. You should see traces for each email processed. Each trace will show:
   - `lookup_employee` → `classify_query` → `rag_lookup` (which contains the sub-trace for the RAG agent: `analyze_query` → `retrieve` → `generate_answer` → `check_escalation`) → `handle_{department}`.
4. Click on the `analyze_query` step to verify `target_country` was correctly extracted.
5. Click on `retrieve` to see which documents were returned and their country metadata.

**If you still see no traces:**
- Check that your API key is valid: go to [https://smith.langchain.com/settings](https://smith.langchain.com/settings) and verify the key.
- Check that `config.py` is loaded before any LangChain imports. Since `graph.py` imports `config` at the top, this should happen automatically.
- In the `mail_processor.py` terminal, add this temporary debug line at the top of `process_email()`:
  ```python
  import os
  print("TRACING:", os.environ.get("LANGCHAIN_TRACING_V2"))
  print("PROJECT:", os.environ.get("LANGCHAIN_PROJECT"))
  print("API KEY SET:", bool(os.environ.get("LANGCHAIN_API_KEY")))
  ```
  All three should print `true`, your project name, and `True`.

---

## Troubleshooting: Common Issues

### "Sender not found in employee database"
Your personal email is not in the Postgres `employees` table. Update `employee_data.csv` with your sending email, then re-seed:
```bash
dropdb hr_system && createdb hr_system && python seed_db.py && python embed_documents.py
```

### Reply comes from wrong department email
This should now be fixed. The RAG agent's document metadata overrides the classifier. If it still happens:
1. Check the `mail_processor.py` logs — look for `department:` in the output.
2. Check LangSmith trace → `rag_lookup` step → see if `department` was overridden.
3. If the documents don't have `escalation_department` metadata, rebuild the FAISS index.

### FAISS returns wrong country's documents
1. Delete the old index: `rm -rf faiss_index/`
2. Rebuild: `python embed_documents.py`
3. Verify with the Python snippet in Step 4 above.

### "IMAP error: AUTHENTICATIONFAILED"
- Use an **App Password**, not your normal Gmail password.
- Ensure **IMAP is enabled** in Gmail Settings → Forwarding and POP/IMAP.
- Run `python test_email_connection.py`.

### "Found 0 unread email(s)"
- The email may be in Spam — check the HR inbox's Spam folder.
- The email may already be marked as Read — mark it as Unread in the HR inbox.
- Wait for the next poll cycle (30 seconds).

### No LangSmith traces
- Your `.env` must have a valid `LANGCHAIN_API_KEY` (or `LANGSMITH_API_KEY`).
- `config.py` now handles both naming conventions automatically.
- Traces appear after the workflow completes — wait for the reply email before checking.

---

## Phase 2: Production Deployment & Hardening (Future)

### 1. Infrastructure & Hosting
- **Database:** Migrate from local Postgres to a managed database (e.g., AWS RDS, Supabase, Neon).
- **Vector Store:** Migrate from local FAISS to `pgvector` (inside your Postgres DB) or a managed vector DB like Pinecone so the index isn't lost when the server restarts.
- **Compute:** Deploy the FastAPI server (web service) and the Mail Processor (background worker) to a cloud provider like AWS ECS, Render, or Railway.

### 2. Document Management API
- Currently, updating HR documents requires a developer to run `python embed_documents.py`.
- Add a `POST /documents/upload` endpoint in `main.py` that allows HR admins to upload new `.docx` files, automatically parse, chunk, embed, and update the database/vector store.

### 3. Conversation Memory
- Add a `conversations` table to track email threads and allow the bot to remember context from previous exchanges.

### 4. Multi-Language Support
- For countries like Brazil (Portuguese) and Argentina (Spanish), add automatic translation or bilingual response generation.

### 5. Monitoring & Alerting
- Set up alerts for failed email sends, high escalation rates, or RAG retrieval failures.
- Use LangSmith evaluations to track answer quality over time.
