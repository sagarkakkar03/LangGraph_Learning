# HR System Project Structure

This document provides a high-level overview of the files and architecture of the `HR_system` project.

## Core Application Logic

* **`config.py`**
  Centralized configuration file. Loads environment variables, sets up LangSmith observability, defines IMAP/SMTP settings, and holds the metadata/prompts for all HR departments (e.g., keywords, system prompts, routing mappings).

* **`graph.py`**
  The main LangGraph workflow for processing incoming emails. It handles:
  1. Looking up the sender in the employee database.
  2. Ignoring unauthorized senders.
  3. Classifying the query using an LLM.
  4. Invoking the RAG agent for policy answers.
  5. Routing to the specific department handler to draft and send the final email response.

* **`rag_agent.py`**
  A specialized LangGraph sub-workflow dedicated to Retrieval-Augmented Generation (RAG). It:
  1. Analyzes the query to determine the target country.
  2. Retrieves relevant document chunks from the FAISS vector store.
  3. Generates a grounded answer based *only* on the retrieved policies.
  4. Checks if the query needs human escalation based on document rules, attachments, or sensitive topics.

* **`email_service.py`**
  Handles all direct interactions with email protocols.
  - **IMAP:** Fetches unread emails, parses headers, extracts bodies, and detects attachments.
  - **SMTP:** Sends automated replies and forwards escalated queries to department inboxes, maintaining proper email threading.

* **`mail_processor.py`**
  The background worker script. It runs continuously, polling the HR inbox via IMAP at a set interval (e.g., every 30 seconds), and feeds new emails into the main LangGraph workflow (`graph.py`).

* **`main.py`**
  A FastAPI application that exposes REST endpoints for the system (e.g., `/send` for manual testing, `/ask` for direct RAG queries, and endpoints to view employee/department data).

## Database & Data Models

* **`database.py`**
  Contains the SQLAlchemy ORM models and database connection logic for PostgreSQL. Defines tables for `Employee`, `Department`, `HRDocument`, `HRDocumentChunk`, and `HREscalationRule`.

## Data Seeding & Embedding Scripts

* **`seed_db.py`**
  Initializes the database tables and seeds the initial employee data from the CSV.

* **`seed_documents.py`**
  Reads the document metadata CSV and populates the `hr_documents` and `hr_escalation_rules` tables in the database.

* **`embed_documents.py`**
  Reads the actual `.docx` files, chunks the text, generates embeddings via OpenAI, builds the FAISS vector index (saved to `faiss_index/`), and backfills the chunk text into the PostgreSQL database.

## Datasets & Configuration Files

* **`employee_data.csv`**
  Dummy dataset containing employee records (Name, Email, Grade, Department, Country, Manager status) used to populate the database.

* **`hr_document_data.csv`**
  Metadata for the HR policy documents (Document Code, Title, Country, Category, Escalation Email, etc.).

* **`.env` / `.env.example`**
  Environment variables for API keys (OpenAI, LangSmith), database URLs, and email credentials.

* **`requirements.txt`**
  Python dependencies required to run the project (LangGraph, FastAPI, SQLAlchemy, FAISS, etc.).

## Utilities & Documentation

* **`test_email_connection.py`**
  A standalone utility script to verify that the provided IMAP and SMTP credentials in the `.env` file are working correctly.

* **`NEXT_STEPS.md`**
  A detailed guide for local testing, troubleshooting common issues (like email connectivity or LangSmith tracing), and steps for production deployment.
