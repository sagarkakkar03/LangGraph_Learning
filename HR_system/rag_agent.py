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

from config import (
    OPENAI_MODEL,
    EMBEDDING_MODEL,
    FAISS_INDEX_DIR,
    RAG_TOP_K,
)
from database import SessionLocal, HREscalationRule

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

    retrieved_chunks: list[dict] = []
    source_docs: list[str] = []
    answer: str = ""

    needs_escalation: bool = False
    escalation_email: Optional[str] = None
    escalation_department: Optional[str] = None
    escalation_reason: Optional[str] = None


class EscalationDecision(BaseModel):
    needs_escalation: bool = Field(
        description="Whether this query needs human escalation beyond the automated answer"
    )
    reason: str = Field(description="Why escalation is or is not needed")


# ------------------------------------------------------------------ #
#  Nodes
# ------------------------------------------------------------------ #

def retrieve(state: RAGState):
    if vectorstore is None:
        return {"retrieved_chunks": [], "source_docs": []}

    filters = {}
    if state.sender_country:
        filters["country"] = state.sender_country

    if filters:
        results = vectorstore.similarity_search(
            state.query,
            k=RAG_TOP_K,
            filter=filters,
        )
        if len(results) < 3:
            results = vectorstore.similarity_search(state.query, k=RAG_TOP_K)
    else:
        results = vectorstore.similarity_search(state.query, k=RAG_TOP_K)

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
        })
        source_codes.add(f"{meta.get('doc_code', '')} — {meta.get('title', '')}")

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
        context_parts.append(
            f"[{i}] {chunk['title']} ({chunk['doc_code']}, {chunk['country']}, "
            f"{chunk['category']})\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = (
        "You are an HR assistant. Answer the employee's question using ONLY the "
        "HR policy documents provided below. Be specific, cite the document code "
        "and title when referencing a policy, and be professional.\n\n"
        "If the documents don't fully answer the question, say what you can "
        "and note that the employee should contact the relevant team for more details.\n\n"
        f"## Retrieved HR Documents\n\n{context}\n\n"
        f"## Employee Question\n\n{state.query}\n\n"
        "## Your Answer"
    )

    answer = model.invoke(prompt).content
    return {"answer": answer}


def check_escalation(state: RAGState):
    if not state.retrieved_chunks:
        return {
            "needs_escalation": True,
            "escalation_reason": "No relevant documents found — needs human review.",
        }

    categories = {c["category"] for c in state.retrieved_chunks}
    esc_emails = {c["escalation_email"] for c in state.retrieved_chunks if c["escalation_email"]}
    esc_email = next(iter(esc_emails), None)

    if state.has_attachments:
        return {
            "needs_escalation": True,
            "escalation_email": esc_email,
            "escalation_reason": "Email contains attachments that require human review.",
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

    escalation_checker = model.with_structured_output(EscalationDecision)
    decision = escalation_checker.invoke(
        f"Based on this employee query, does it need human escalation "
        f"beyond an automated policy-based answer? Consider if it involves "
        f"personal grievances, legal issues, salary disputes, or harassment.\n\n"
        f"Query: {state.query}\n\n"
        f"Categories found: {', '.join(categories)}"
    )

    if decision.needs_escalation:
        return {
            "needs_escalation": True,
            "escalation_email": esc_email,
            "escalation_reason": decision.reason,
        }

    return {"needs_escalation": False}


# ------------------------------------------------------------------ #
#  Graph
# ------------------------------------------------------------------ #

rag_graph = StateGraph(RAGState)

rag_graph.add_node("retrieve", retrieve)
rag_graph.add_node("generate_answer", generate_answer)
rag_graph.add_node("check_escalation", check_escalation)

rag_graph.add_edge(START, "retrieve")
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
