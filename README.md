# OMEGA - HR Email Routing & RAG Agent 🤖

An intelligent, autonomous HR email routing and response system built with **LangGraph**, **FastAPI**, and **Streamlit**. 

OMEGA reads incoming HR emails, classifies them by department, uses Retrieval-Augmented Generation (RAG) to answer policy questions based on company documents, and automatically escalates sensitive or complex queries to human HR representatives.

## 🌟 Features

- **Automated Email Processing**: Continuously monitors an inbox via IMAP.
- **Intelligent Routing**: Classifies queries into departments (People Team, Payroll, Benefits, IT Support, etc.).
- **RAG-Powered Responses**: Answers employee questions using a Pinecone vector database of embedded HR policy documents.
- **Smart Escalation**: Automatically forwards emails to human representatives if the query is sensitive, contains attachments, or if the AI has low confidence.
- **Multi-Country Support**: Handles policies specific to different regions (e.g., US, India, Brazil, Argentina).
- **Observability**: Fully integrated with LangSmith for tracing, debugging, and benchmarking.
- **Interactive UI**: Includes a Streamlit dashboard for local testing and a LangServe playground.

## 🏗️ Architecture

- **Workflow Orchestration**: LangGraph
- **LLM & Embeddings**: OpenAI (`gpt-4o-mini`, `text-embedding-3-small`)
- **Vector Store**: Faiss
- **Database**: PostgreSQL (SQLAlchemy ORM) (Cloud Superbase)
- **API Framework**: FastAPI & LangServe
- **Frontend**: Streamlit

---

## 🚀 Getting Started (Local Development)

### Prerequisites
- Python 3.11+
- PostgreSQL is installed and running locally
- OpenAI API Key
- Gmail account with App Passwords enabled (for IMAP/SMTP)
- [LangSmith](https://smith.langchain.com/) account (optional, for observability)

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd HR_system
```

### 2. Set up Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory (you can copy from `.env.example` if available) and fill in your credentials:
```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Email Configuration
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=your_hr_email@gmail.com
IMAP_PASSWORD=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_hr_email@gmail.com
SMTP_PASSWORD=your_app_password

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/hr_database

# Pinecone (Vector Store)
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=hr-docs

# LangSmith (Observability)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=hr-email-routing
```

### 4. Database Setup & Data Seeding
Ensure your PostgreSQL server is running and the database specified in `DATABASE_URL` is created. Then run the setup scripts:

```bash
# 1. Seed the database with employees and departments
python scripts/seed_db.py

# 2. Seed the database with HR document metadata
python scripts/seed_documents.py

# 3. Embed the actual .docx files into the Pinecone vector store
python scripts/embed_documents.py
```

### 5. Running the Application

You can run different components of the system depending on your needs:

**A. Run the Streamlit Testing UI**
Great for testing the agent without sending actual emails.
```bash
streamlit run streamlit_app.py
```

**B. Run the FastAPI Backend & LangServe**
Provides REST API endpoints and a LangServe playground at `http://localhost:8000/hr-agent/playground`.
```bash
python run_api.py
```

**C. Run the Background Email Worker**
Continuously listens to the configured inbox and processes live emails.
```bash
python run_worker.py
```

---

## 🐳 Running with Docker

You can easily spin up the entire stack (API, Worker, and Streamlit) using Docker Compose.

1. Ensure Docker and Docker Compose are installed.
2. Make sure your `.env` file is fully configured.
3. Run the following command:

```bash
docker-compose up -d --build
```

- **FastAPI / LangServe**: http://localhost:8000
- **Streamlit UI**: http://localhost:8501
- **Email Worker**: Runs in the background

---

## 📁 Project Structure

```text
HR_system/
├── app/
│   ├── agents/         # LangGraph workflows and RAG logic
│   ├── api/            # FastAPI routes and LangServe setup
│   ├── core/           # Configuration and environment variables
│   ├── db/             # SQLAlchemy models and database connection
│   └── services/       # IMAP/SMTP email handling
├── data/               # CSVs
├── DocsHR/             # Raw .docx HR policy files
├── scripts/            # DB seeding, embedding, and evaluation scripts
├── DEPLOYMENT.md       # Cloud deployment instructions
├── docker-compose.yml  # Docker orchestration
├── Dockerfile          # Container definition
├── run_api.py          # FastAPI entry point
├── run_worker.py       # Background email worker entry point
└── streamlit_app.py    # Streamlit UI entry point
```

## ☁️ Deployment

For detailed instructions on deploying this application to production (Streamlit Community Cloud, Render, Railway, or Google Cloud Platform), please refer to [DEPLOYMENT.md](DEPLOYMENT.md).
