"""
RAG Agent — retrieves relevant HR documents and generates grounded answers.

Uses a LangGraph workflow:
  START → retrieve → generate_answer → check_escalation → END

The agent is called by the main email routing workflow when it needs to
answer a question using HR policy documents.
"""

from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import Optional
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from app.core.config import (
    OPENAI_MODEL,
    EMBEDDING_MODEL,
    FAISS_INDEX_DIR,
    RAG_TOP_K,
)
from app.db.database import SessionLocal, HREscalationRule

import os
import logging

logger = logging.getLogger(__name__)

model = ChatOpenAI(model=OPENAI_MODEL)


def _load_vectorstore() -> FAISS | None:
    if not os.path.isdir(FAISS_INDEX_DIR):
        logger.warning("FAISS index not found at %s. Run embed_documents.py first.", FAISS_INDEX_DIR)
        return None
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return FAISS.load_local(FAISS_INDEX_DIR, embeddings, allow_dangerous_deserialization=True)


vectorstore = _load_vectorstore()


# ------------------------------------------------------------------ #
#  State
# ------------------------------------------------------------------ #

class RAGState(BaseModel):
    query: str
    sender_country: Optional[str] = None
    has_attachments: bool = False

    target_country: Optional[str] = None
    human_requested: bool = False
    auto_reply_eligible: bool = True
    confidence: Optional[str] = None
    retrieved_chunks: list[dict] = []
    source_docs: list[str] = []
    answer: str = ""

    needs_escalation: bool = False
    escalation_email: Optional[str] = None
    escalation_department: Optional[str] = None
    escalation_reason: Optional[str] = None


class QueryAnalysis(BaseModel):
    target_country: Optional[str] = Field(
        description="The country explicitly mentioned in the query, if any. "
        "Must be one of: 'India', 'Argentina', 'Brazil', 'Pakistan', 'United States'. "
        "If 'USA' or 'US' is mentioned, return 'United States'. "
        "If no country is mentioned, return None."
    )
    human_requested: bool = Field(
        default=False,
        description="True if the user explicitly asks to speak to a human, an operator, or asks for escalation."
    )
    query_nature: str = Field(
        description="Classify the nature of this query. Must be one of: "
        "'informational' — the user is simply asking for factual information, policy details, dates, eligibility, etc. "
        "'action_required' — the user needs something done (e.g. apply for leave, update records, file a complaint). "
        "'sensitive' — the query involves personal issues, grievances, legal matters, harassment, or emotional distress. "
        "'ambiguous' — the query is unclear or could go either way."
    )
    confidence: str = Field(
        description="How confidently can this query be answered from standard HR policy documents? "
        "Must be one of: 'high', 'medium', 'low'."
    )


class EscalationDecision(BaseModel):
    needs_escalation: bool = Field(
        description="Whether this query needs human escalation beyond the automated answer"
    )
    reason: str = Field(description="Why escalation is or is not needed")


# ------------------------------------------------------------------ #
#  Nodes
# ------------------------------------------------------------------ #

def analyze_query(state: RAGState):
    """Determine query intent, target country, and whether the bot should auto-reply."""
    analyzer = model.with_structured_output(QueryAnalysis)
    result = analyzer.invoke(
        "Analyze this HR query. Determine:\n"
        "1. If it asks about a specific country's policy.\n"
        "2. If the user wants a human operator.\n"
        "3. The nature of the query (informational / action_required / sensitive / ambiguous).\n"
        "4. Whether standard HR policy documents can answer this with high / medium / low confidence.\n\n"
        f"Query: {state.query}"
    )
    
    sender_country = state.sender_country
    if sender_country and sender_country.upper() in ["USA", "US"]:
        sender_country = "United States"

    target_country = result.target_country or sender_country

    # Only auto-reply for passive informational queries with high confidence.
    # Everything else gets forwarded to a human.
    auto_reply = (
        result.query_nature == "informational"
        and result.confidence == "high"
        and not result.human_requested
    )

    logger.info(
        "Query analysis: nature=%s, confidence=%s, human_requested=%s, auto_reply=%s",
        result.query_nature, result.confidence, result.human_requested, auto_reply,
    )

    return {
        "target_country": target_country,
        "human_requested": result.human_requested,
        "auto_reply_eligible": auto_reply,
        "confidence": result.confidence,
    }


def retrieve(state: RAGState):
    if vectorstore is None:
        return {"retrieved_chunks": [], "source_docs": []}

    kwargs = {"k": RAG_TOP_K, "fetch_k": 400}
    if state.target_country:
        kwargs["filter"] = {"country": state.target_country}

    # We use a high fetch_k because FAISS fetches first, then filters.
    # We DO NOT fallback to an unfiltered search if results are low, 
    # because giving an employee another country's HR policy is a compliance risk.
    results = vectorstore.similarity_search(state.query, **kwargs)

    chunks = []
    source_codes = set()
    for doc in results:
        meta = doc.metadata
        chunks.append({
            "text": doc.page_content,
            "doc_code": meta.get("doc_code", ""),
            "title": meta.get("title", ""),
            "category": meta.get("category", ""),
            "country": meta.get("country", ""),
            "doc_type": meta.get("doc_type", ""),
            "escalation_email": meta.get("escalation_email", ""),
            "escalation_department": meta.get("escalation_department", ""),
            "document_url": meta.get("document_url", ""),
        })
        url = meta.get("document_url", "")
        if url:
            source_codes.add(f"{meta.get('title', '')} ({url})")
        else:
            source_codes.add(f"{meta.get('title', '')}")

    return {
        "retrieved_chunks": chunks,
        "source_docs": sorted(source_codes),
    }


def generate_answer(state: RAGState):
    if not state.retrieved_chunks:
        return {
            "answer": (
                "I couldn't find relevant HR documents for your query. "
                "Please contact hr@company.com directly for assistance."
            )
        }

    context_parts = []
    for i, chunk in enumerate(state.retrieved_chunks, 1):
        url_info = f", URL: {chunk['document_url']}" if chunk.get('document_url') else ""
        context_parts.append(
            f"[{i}] {chunk['title']} ({chunk['country']}, "
            f"{chunk['category']}{url_info})\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = (
        f"You are OMEGA, an AI HR assistant for employees based in {state.target_country or 'the company'}. "
        "Answer the employee's question using ONLY the HR policy documents provided below. "
        "Be specific, cite the document title when referencing a policy, and be professional.\n\n"
        "If the document has a URL provided in the context, please include the URL in your response so the user can read the full document.\n\n"
        "If the documents don't fully answer the question for their specific country, say what you can "
        "and note that the employee should contact the relevant team for more details. DO NOT use or mention policies from other countries.\n\n"
        "IMPORTANT: Output plain text only. Do NOT use any markdown formatting (like **bold** or *italics*).\n\n"
        f"## Retrieved HR Documents\n\n{context}\n\n"
        f"## Employee Question\n\n{state.query}\n\n"
        "## Your Answer"
    )

    answer = model.invoke(prompt).content
    return {"answer": answer}


def check_escalation(state: RAGState):
    categories = {c["category"] for c in state.retrieved_chunks} if state.retrieved_chunks else set()
    esc_emails = {c["escalation_email"] for c in state.retrieved_chunks if c.get("escalation_email")} if state.retrieved_chunks else set()
    esc_email = next(iter(esc_emails), None)

    if state.human_requested:
        return {
            "needs_escalation": True,
            "escalation_email": esc_email,
            "escalation_reason": "User explicitly requested a human operator or escalation.",
        }

    sensitive_keywords = ["harass", "assault", "discriminate", "threat", "bully", "bullying", "suicide", "abuse"]
    query_lower = state.query.lower()
    if any(kw in query_lower for kw in sensitive_keywords):
        return {
            "needs_escalation": True,
            "escalation_email": esc_email,
            "escalation_reason": "Query contains highly sensitive keywords requiring immediate human review.",
        }

    if not state.retrieved_chunks:
        return {
            "needs_escalation": True,
            "escalation_reason": "No relevant documents found — needs human review.",
        }

    if state.has_attachments:
        return {
            "needs_escalation": True,
            "escalation_email": esc_email,
            "escalation_reason": "Email contains attachments that require human review.",
        }

    # If the query analysis determined this is NOT a passive informational query,
    # escalate it — only high-confidence informational queries get auto-replied.
    if not state.auto_reply_eligible:
        reason = (
            f"Query classified as non-informational or low/medium confidence "
            f"(confidence: {state.confidence}). Forwarding to human HR team."
        )
        return {
            "needs_escalation": True,
            "escalation_email": esc_email,
            "escalation_reason": reason,
        }

    db = SessionLocal()
    try:
        for category in categories:
            rule = (
                db.query(HREscalationRule)
                .filter(HREscalationRule.category == category)
                .first()
            )
            if rule and rule.auto_escalate:
                return {
                    "needs_escalation": True,
                    "escalation_email": rule.escalation_email,
                    "escalation_department": rule.escalation_department,
                    "escalation_reason": (
                        f"Category '{category}' (sensitivity: {rule.sensitivity}) "
                        f"requires automatic escalation to {rule.escalation_department}."
                    ),
                }
    finally:
        db.close()

    return {"needs_escalation": False}


# ------------------------------------------------------------------ #
#  Graph
# ------------------------------------------------------------------ #

rag_graph = StateGraph(RAGState)

rag_graph.add_node("analyze_query", analyze_query)
rag_graph.add_node("retrieve", retrieve)
rag_graph.add_node("generate_answer", generate_answer)
rag_graph.add_node("check_escalation", check_escalation)

rag_graph.add_edge(START, "analyze_query")
rag_graph.add_edge("analyze_query", "retrieve")
rag_graph.add_edge("retrieve", "generate_answer")
rag_graph.add_edge("generate_answer", "check_escalation")
rag_graph.add_edge("check_escalation", END)

rag_workflow = rag_graph.compile()


# ------------------------------------------------------------------ #
#  Public API
# ------------------------------------------------------------------ #

def ask_hr(query: str, sender_country: str | None = None, has_attachments: bool = False) -> dict:
    """Run a query through the RAG agent and return the full result."""
    result = rag_workflow.invoke({
        "query": query,
        "sender_country": sender_country,
        "has_attachments": has_attachments,
    })
    return result
