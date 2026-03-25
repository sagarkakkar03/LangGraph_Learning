# HR System Project Structure

This document provides a high-level overview of the files and architecture of the `HR_system` project, which follows a standard modern Python layout.

## Directory Layout

```text
HR_system/
├── app/                  # Main application code
│   ├── api/              # FastAPI application and endpoints
│   ├── agents/           # LangGraph workflows and AI agents
│   ├── core/             # Centralized configuration and settings
│   ├── db/               # Database models and connection logic
│   └── services/         # External service integrations (Email, etc.)
├── data/                 # Datasets, documents, and vector store
├── docs/                 # Project documentation
├── scripts/              # CLI scripts for seeding and embedding
├── run_api.py            # Entry point to run the FastAPI server
├── run_worker.py         # Entry point to run the background mail processor
├── .env                  # Environment variables
└── requirements.txt      # Python dependencies
```

## Core Application Logic (`app/`)

* **`app/core/config.py`**
  Centralized configuration file. Loads environment variables, sets up LangSmith observability, defines IMAP/SMTP settings, and holds the metadata/prompts for all HR departments.

* **`app/agents/graph.py`**
  The main LangGraph workflow for processing incoming emails. It handles:
  1. Looking up the sender in the employee database.
  2. Ignoring unauthorized senders.
  3. Classifying the query using an LLM.
  4. Invoking the RAG agent for policy answers.
  5. Routing to the specific department handler to draft and send the final email response.

* **`app/agents/rag_agent.py`**
  A specialized LangGraph sub-workflow dedicated to Retrieval-Augmented Generation (RAG). It:
  1. Analyzes the query to determine the target country.
  2. Retrieves relevant document chunks from the FAISS vector store.
  3. Generates a grounded answer based *only* on the retrieved policies.
  4. Checks if the query needs human escalation based on document rules, attachments, or sensitive topics.

* **`app/services/email_service.py`**
  Handles all direct interactions with email protocols.
  - **IMAP:** Fetches unread emails, parses headers, extracts bodies, and detects attachments.
  - **SMTP:** Sends automated replies and forwards escalated queries to department inboxes, maintaining proper email threading.

* **`app/db/database.py`**
  Contains the SQLAlchemy ORM models and database connection logic for PostgreSQL. Defines tables for `Employee`, `Department`, `HRDocument`, `HRDocumentChunk`, and `HREscalationRule`.

* **`app/api/main.py`**
  A FastAPI application that exposes REST endpoints for the system (e.g., `/send` for manual testing, `/ask` for direct RAG queries, and endpoints to view employee/department data).

## Entry Points (Root)

* **`run_worker.py`**
  The background worker script. It runs continuously, polling the HR inbox via IMAP at a set interval (e.g., every 30 seconds), and feeds new emails into the main LangGraph workflow.

* **`run_api.py`**
  The entry point to start the FastAPI web server using Uvicorn.

## Data Seeding & Embedding Scripts (`scripts/`)

* **`scripts/seed_db.py`**
  Initializes the database tables and seeds the initial employee data from the CSV.

* **`scripts/seed_documents.py`**
  Reads the document metadata CSV and populates the `hr_documents` and `hr_escalation_rules` tables in the database.

* **`scripts/embed_documents.py`**
  Reads the actual `.docx` files, chunks the text, generates embeddings via OpenAI, builds the FAISS vector index (saved to `data/faiss_index/`), and backfills the chunk text into the PostgreSQL database.

* **`scripts/test_email_connection.py`**
  A standalone utility script to verify that the provided IMAP and SMTP credentials in the `.env` file are working correctly.

## Datasets & Assets (`data/`)

* **`data/employee_data.csv`**
  Dummy dataset containing employee records used to populate the database.

* **`data/hr_document_data.csv`**
  Metadata for the HR policy documents.

* **`data/DocsHR/`**
  The raw `.docx` HR policy documents.

* **`data/faiss_index/`**
  The generated FAISS vector store used for RAG retrievals.
