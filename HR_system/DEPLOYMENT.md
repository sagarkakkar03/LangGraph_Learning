# Deployment Guide: HR Email Routing & RAG Agent

This guide outlines the steps to take this application from your local machine to a production cloud environment.

## 1. Prerequisites (Cloud Database)
Currently, your application uses a local PostgreSQL database (`localhost:5432`). To deploy to the cloud, you need a hosted database.
* **Action:** Create a free managed PostgreSQL database using [Supabase](https://supabase.com/), [Neon](https://neon.tech/), or [Render](https://render.com/).
* **Update:** Get the new `DATABASE_URL` from your provider and update your `.env` file.
* **Seed:** Run your seed scripts locally against the new cloud database to populate employees and documents:
  ```bash
  python scripts/seed_db.py
  python scripts/seed_documents.py
  ```

## 2. Handling the Vector Database (FAISS)
FAISS creates local files (`index.faiss`, `index.pkl`). In a serverless cloud environment (like Render or Heroku), local files can be wiped out when the server restarts.
* **Short-term fix:** Add a step in your deployment command to rebuild the index on startup: `python scripts/embed_documents.py && uvicorn app.api.main:app`
* **Long-term fix:** Migrate from FAISS to a cloud vector database like **Pinecone**, **Weaviate**, or **pgvector** (since you already use Postgres).

---

## Deployment Option A: Streamlit Community Cloud (Easiest for UI)
If you just want to share the interactive web UI with others, Streamlit provides free hosting.

1. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Click **New app**.
3. Select your GitHub repository (`HR_Cortex` or `LangGraph_Learning`).
4. Set the Main file path to: `HR_system/streamlit_app.py`.
5. Click **Advanced settings** and paste the contents of your `.env` file (OpenAI API key, Cloud Postgres URL, etc.) into the Secrets box.
6. Click **Deploy!**
*(Note: Streamlit will run the LangGraph workflow directly. It will not run the FastAPI server or the background email worker).*

---

## Deployment Option B: Render or Railway (Full System)
To run the full system (FastAPI backend, LangServe, Streamlit UI, and the Background Email Worker), use a platform like [Render](https://render.com/) or [Railway](https://railway.app/).

### 1. Deploy the FastAPI Backend (LangServe)
* Create a new **Web Service**.
* Connect your GitHub repo.
* **Build Command:** `pip install -r requirements.txt && python scripts/embed_documents.py`
* **Start Command:** `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`
* **Environment Variables:** Add all variables from your `.env` file.

### 2. Deploy the Background Email Worker
* Create a new **Background Worker** (in Render/Railway).
* Connect the same GitHub repo.
* **Build Command:** `pip install -r requirements.txt && python scripts/embed_documents.py`
* **Start Command:** `python run_worker.py`
* **Environment Variables:** Add all variables from your `.env` file.

### 3. Deploy the Streamlit App (Optional)
* Create another **Web Service**.
* **Build Command:** `pip install -r requirements.txt`
* **Start Command:** `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`

---

## 3. Final Production Checklist
- [ ] **Security:** Ensure `IMAP_PASSWORD` and `SMTP_PASSWORD` use App Passwords (if using Gmail), not your real password.
- [ ] **Observability:** Ensure `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` are set in your cloud environment so you can monitor production runs.
- [ ] **Error Handling:** Check LangSmith regularly for failed runs or hallucinated responses to improve your RAG prompts.