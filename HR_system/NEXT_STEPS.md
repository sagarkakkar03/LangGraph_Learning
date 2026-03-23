# HR Email Routing & RAG System: Next Steps to Production

This document outlines the remaining steps required to take our HR email routing and RAG-based automated response system from its current functional state to a fully deployed, production-ready application.

## Current State of the Codebase

We have built a robust, multi-agent HR system with the following components:
1. **Postgres Database (`database.py`)**: Stores employees, departments, HR document metadata, and escalation rules.
2. **Data Seeding (`seed_db.py`, `seed_documents.py`)**: Scripts to populate the DB from CSVs.
3. **Document Embedding (`embed_documents.py`)**: Reads `.docx` files, chunks them, and builds a FAISS vector index.
4. **RAG Agent (`rag_agent.py`)**: A LangGraph workflow that retrieves relevant policy chunks based on the user's query and country, generates a grounded answer, and determines if human escalation is needed.
5. **Email Workflow (`graph.py`)**: The main LangGraph workflow. It looks up the employee, classifies the query into a department, runs the RAG agent to get policy context, and drafts a final email response.
6. **Email Service (`email_service.py`)**: Handles reading unread emails via IMAP and sending/forwarding emails via SMTP.
7. **Mail Processor (`mail_processor.py`)**: A daemon that polls the inbox every 30 seconds and feeds new emails into the workflow.
8. **API Server (`main.py`)**: A FastAPI server providing endpoints for direct RAG queries (`/ask`) and employee/department lookups.

## Phase 1: Local Testing & Validation

Before deploying, we need to ensure the system works flawlessly end-to-end in a local environment.

### 1. Environment Setup
- [ ] Create a `.env` file based on `.env.example`.
- [ ] Add a valid `OPENAI_API_KEY`.
- [ ] Set up a local Postgres instance and update `DATABASE_URL`.
- [ ] Configure `LANGSMITH_API_KEY` to enable tracing and observability.

### 2. Email Configuration (Crucial Step)
- [ ] Set up a dedicated testing email account (e.g., a Gmail account like `hr-test-bot@gmail.com`).
- [ ] Generate an **App Password** for this account (standard passwords won't work for IMAP/SMTP).
- [ ] Update `.env` with the IMAP and SMTP credentials.
- [ ] For local testing, point all department emails (`EMAIL_PEOPLE_TEAM`, `EMAIL_PAYROLL`, etc.) to this same testing email address, or use email aliases (e.g., `hr-test-bot+payroll@gmail.com`) so you can see the routing happen without needing 9 separate inboxes.

### 3. Data Ingestion
- [ ] Run `python seed_db.py` to populate Postgres with employees and document metadata.
- [ ] Run `python embed_documents.py` to process the `DocsHR/` folder and build the FAISS index. Verify no errors occur during parsing.

### 4. End-to-End Email Test
- [ ] Start the polling daemon: `python mail_processor.py`.
- [ ] Send an email from a personal account (that matches an employee in `employee_data.csv`) to the testing HR inbox.
  - *Test 1 (Standard)*: "What is the parental leave policy?" -> Should auto-reply with the policy.
  - *Test 2 (Escalation)*: "I am being harassed by my manager." -> Should auto-escalate to Employee Relations/Compliance without trying to resolve it purely via docs.
- [ ] Verify the LangSmith traces to ensure the RAG agent is retrieving the correct documents and the escalation logic is firing correctly.

## Phase 2: System Hardening & Edge Cases

### 1. Email Threading & History
- **Current Limitation**: The system treats every email as a brand new query. It does not understand reply chains.
- **Action**: Update `email_service.py` to extract the `In-Reply-To` or `References` headers. Update `graph.py` to fetch previous conversation history (either from the email body or a database table) so the LLM has context of the ongoing thread.

### 2. Unrecognized Employees
- **Current State**: If an email comes from an unknown address, `lookup_employee` returns empty context, but the system still tries to answer.
- **Action**: Decide on a policy. Should we reject emails from non-company domains? Should we have a generic fallback? Update `graph.py` to handle `state.employee_name == None` gracefully (e.g., "We could not verify your employee ID. Please email from your company address.").

### 3. Attachments
- **Current State**: `_extract_body` in `email_service.py` ignores attachments.
- **Action**: If employees submit medical certificates or expense receipts, the system currently drops them. We need to either forward attachments to the department inbox or use a multimodal model to read them.

### 4. Vector Store Scalability
- **Current State**: Using local FAISS.
- **Action**: If deployed to the cloud (e.g., AWS/GCP), a local FAISS folder on disk is fragile (ephemeral storage). Migrate from FAISS to a managed vector database (like pgvector within our existing Postgres DB, or Pinecone/Weaviate).

## Phase 3: Deployment & Infrastructure

### 1. Containerization
- [ ] Create a `Dockerfile` that installs dependencies, copies the code, and sets the entrypoint.
- [ ] Create a `docker-compose.yml` to run the FastAPI server, the Mail Processor daemon, and the Postgres database together.

### 2. Cloud Hosting
- [ ] **Database**: Provision a managed Postgres database (e.g., AWS RDS, Supabase, Neon).
- [ ] **Compute**: Deploy the FastAPI server and the Mail Processor as separate services (e.g., AWS ECS, Render, Railway, or Heroku). The Mail Processor must run as a continuous background worker.

### 3. Production Email Setup
- [ ] Work with IT to provision the actual `hr@company.com` inbox and the 8 department inboxes.
- [ ] Obtain secure OAuth2 or App Password credentials for the production IMAP/SMTP servers.
- [ ] Update production environment variables.

### 4. CI/CD & Document Updates
- **Current State**: Documents are embedded manually via `embed_documents.py`.
- **Action**: Create an admin endpoint in FastAPI (e.g., `POST /documents/upload`) that allows HR to upload a new `.docx` file. The endpoint should automatically chunk the file, update Postgres, and update the vector store, ensuring the RAG agent always has the latest policies without requiring a developer to run a script.

## Phase 4: Monitoring & Analytics

1. **LangSmith Dashboards**: Set up custom dashboards in LangSmith to track:
   - Escalation rates (how often does the AI fail to answer?).
   - Most frequently asked questions/categories.
   - Token usage and LLM costs per department.
2. **Error Alerts**: Integrate Sentry or a similar tool in `mail_processor.py` so that if IMAP disconnects or the LLM API goes down, the engineering team is alerted immediately.
