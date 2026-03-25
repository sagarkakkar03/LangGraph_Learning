"""
Main email routing workflow.

START → lookup_employee → (valid?) → classify_query → rag_lookup → handle_{dept} → END
                           └─ ignore_unrecognized → END
"""

from collections import Counter
from typing import Optional

from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from sqlalchemy import func

from app.core.config import (
    OPENAI_MODEL,
    EMAIL_ADDRESSES,
    DEPARTMENTS,
    DEPARTMENT_KEYS,
    CLASSIFIER_PROMPT_TEMPLATE,
    DOC_ESCALATION_TO_DEPT,
)
from app.services.email_service import forward_to_department
from app.db.database import SessionLocal, Employee
from app.agents.rag_agent import ask_hr

model = ChatOpenAI(model=OPENAI_MODEL)


class DepartmentClassification(BaseModel):
    department: str = Field(
        description="The department this query should be routed to. "
        f"Must be one of: {', '.join(DEPARTMENT_KEYS)}"
    )
    reasoning: str = Field(description="Brief reasoning for the classification")


class HRState(BaseModel):
    query: str
    subject: str = ""
    sender_email: str = ""
    message_id: str = ""
    in_reply_to: str = ""
    has_attachments: bool = False
    employee_name: Optional[str] = None
    employee_id: Optional[str] = None
    employee_grade: Optional[str] = None
    employee_department: Optional[str] = None
    employee_country: Optional[str] = None
    is_manager: Optional[bool] = None
    department: Optional[str] = None
    target_email: Optional[str] = None
    response: Optional[str] = None
    reasoning: Optional[str] = None
    rag_answer: Optional[str] = None
    rag_sources: Optional[list[str]] = None
    rag_escalation: Optional[dict] = None
    email_status: Optional[dict] = None


classifier = model.with_structured_output(DepartmentClassification)


# ------------------------------------------------------------------ #
#  Nodes
# ------------------------------------------------------------------ #

def lookup_employee(state: HRState):
    db = SessionLocal()
    try:
        emp = db.query(Employee).filter(func.lower(Employee.email) == state.sender_email.lower()).first()
        if emp:
            return {
                "employee_name": emp.name,
                "employee_id": emp.employee_id,
                "employee_grade": emp.grade,
                "employee_department": emp.department.name,
                "employee_country": emp.country,
                "is_manager": emp.is_manager,
            }
        return {}
    finally:
        db.close()


def check_employee_valid(state: HRState) -> str:
    return "classify_query" if state.employee_name else "ignore_unrecognized"


def ignore_unrecognized(state: HRState):
    return {"response": "Ignored: Sender not found in employee database."}


def classify_query(state: HRState):
    context = ""
    if state.employee_name:
        context = (
            f"\n\nSender context: {state.employee_name} ({state.employee_id}), "
            f"Grade {state.employee_grade}, Department: {state.employee_department}, "
            f"Country: {state.employee_country}, "
            f"Manager: {'Yes' if state.is_manager else 'No'}"
        )
    result = classifier.invoke(CLASSIFIER_PROMPT_TEMPLATE.format(query=state.query) + context)
    dept = result.department if result.department in DEPARTMENT_KEYS else DEPARTMENT_KEYS[0]
    return {
        "department": dept,
        "target_email": EMAIL_ADDRESSES[dept],
        "reasoning": result.reasoning,
    }


def route_to_department(state: HRState) -> str:
    return f"handle_{state.department}"


def rag_lookup(state: HRState):
    """Run the RAG agent and override the classifier's department when documents disagree."""
    rag_result = ask_hr(
        query=state.query,
        sender_country=state.employee_country,
        has_attachments=state.has_attachments,
    )

    escalation = None
    if rag_result.get("needs_escalation"):
        escalation = {
            "email": rag_result.get("escalation_email"),
            "department": rag_result.get("escalation_department"),
            "reason": rag_result.get("escalation_reason"),
        }

    updates: dict = {
        "rag_answer": rag_result.get("answer", ""),
        "rag_sources": rag_result.get("source_docs", []),
        "rag_escalation": escalation,
    }

    chunks = rag_result.get("retrieved_chunks", [])
    if chunks:
        esc_depts = [c.get("escalation_department") for c in chunks if c.get("escalation_department")]
        if esc_depts:
            mapped = DOC_ESCALATION_TO_DEPT.get(Counter(esc_depts).most_common(1)[0][0])
            if mapped and mapped in DEPARTMENT_KEYS:
                updates["department"] = mapped
                updates["target_email"] = EMAIL_ADDRESSES[mapped]

    return updates


def _make_handler(department: str):
    def handler(state: HRState):
        dept_info = DEPARTMENTS[department]

        escalation_reason = ""
        if state.rag_escalation and state.rag_escalation.get("reason"):
            escalation_reason = state.rag_escalation["reason"]

        if escalation_reason:
            # Escalated: send a fixed acknowledgement, no LLM-generated policy content.
            response_body = (
                f"Dear {state.employee_name or 'Employee'},\n\n"
                "Thank you for reaching out to us. We want you to know that your message "
                "has been received and has been forwarded to our human HR team for review.\n\n"
                "A member of our team will reach out to you directly to address your concern. "
                "Please do not hesitate to contact us again if you have any urgent needs "
                "in the meantime.\n\n"
                f"Warm regards,\n{dept_info['sign_off']}\n\n"
                "---\n"
                "Note: This is an automated acknowledgement. Your query has been escalated "
                "to our human HR team who will review your case and reach out to you directly."
            )
        else:
            # High-confidence informational query: generate a full reply from the LLM.
            sender = state.employee_name or state.sender_email or "an employee"
            if state.employee_name:
                sender = (
                    f"{state.employee_name} ({state.employee_id}, "
                    f"Grade {state.employee_grade}, {state.employee_department}, "
                    f"{state.employee_country})"
                )

            rag_context = ""
            if state.rag_answer:
                sources = "\n".join(f"  - {s}" for s in (state.rag_sources or []))
                rag_context = (
                    f"\n\nRelevant HR policy information retrieved:\n"
                    f"{state.rag_answer}\n\nSources:\n{sources}\n"
                )

            prompt = (
                f"{dept_info['system_prompt']} Write a professional email response to "
                f"this query from {sender}.\n\n"
                f"Query: {state.query}\n{rag_context}\n\n"
                f"Ground your response in the retrieved policy information above. "
                f"Cite specific document titles where applicable. "
                f"If the retrieved information includes URLs to the documents, "
                f"include those URLs in your response.\n\n"
                f"IMPORTANT: Output plain text only. Do NOT use any markdown formatting.\n\n"
                f"Sign off as '{dept_info['sign_off']}'."
            )
            response_body = model.invoke(prompt).content
            response_body += (
                "\n\n---\n"
                "Note: This is an automated reply generated by the HR Assistant. "
                "If this response does not fully address your needs, or if you would like to "
                "escalate this query to a human operator, please reply to this email and let us know."
            )

        employee_info_str = ""
        if state.employee_name:
            employee_info_str = (
                f"Name: {state.employee_name}\n"
                f"ID: {state.employee_id}\n"
                f"Grade: {state.employee_grade}\n"
                f"Department: {state.employee_department}\n"
                f"Country: {state.employee_country}\n"
                f"Manager: {'Yes' if state.is_manager else 'No'}"
            )

        email_status = forward_to_department(
            department=department,
            sender_email=state.sender_email,
            query=state.query,
            response_body=response_body,
            subject=state.subject,
            message_id=state.message_id,
            escalation_reason=escalation_reason,
            employee_info=employee_info_str,
        )
        return {"response": response_body, "email_status": email_status}

    handler.__name__ = f"handle_{department}"
    return handler


# ------------------------------------------------------------------ #
#  Build the graph
# ------------------------------------------------------------------ #

graph = StateGraph(HRState)
graph.add_node("lookup_employee", lookup_employee)
graph.add_node("ignore_unrecognized", ignore_unrecognized)
graph.add_node("classify_query", classify_query)
graph.add_node("rag_lookup", rag_lookup)

handler_names = []
for dept_key in DEPARTMENT_KEYS:
    node_name = f"handle_{dept_key}"
    graph.add_node(node_name, _make_handler(dept_key))
    graph.add_edge(node_name, END)
    handler_names.append(node_name)

graph.add_edge(START, "lookup_employee")
graph.add_conditional_edges("lookup_employee", check_employee_valid)
graph.add_edge("ignore_unrecognized", END)
graph.add_edge("classify_query", "rag_lookup")
graph.add_conditional_edges("rag_lookup", route_to_department, handler_names)

workflow = graph.compile()
