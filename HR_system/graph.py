from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import Optional
from langchain_openai import ChatOpenAI

from config import (
    OPENAI_MODEL,
    EMAIL_ADDRESSES,
    DEPARTMENTS,
    DEPARTMENT_KEYS,
    CLASSIFIER_PROMPT_TEMPLATE,
    HANDLER_PROMPT_TEMPLATE,
)

from email_service import forward_to_department
from database import SessionLocal, Employee
from rag_agent import ask_hr

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


def lookup_employee(state: HRState):
    """Look up sender in the employee database to enrich context."""
    db = SessionLocal()
    try:
        emp = db.query(Employee).filter(Employee.email == state.sender_email).first()
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
    if not state.employee_name:
        return "ignore_unrecognized"
    return "classify_query"


def ignore_unrecognized(state: HRState):
    """Do nothing and end the workflow if sender is not an employee."""
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
    prompt = CLASSIFIER_PROMPT_TEMPLATE.format(query=state.query) + context
    result = classifier.invoke(prompt)
    dept = result.department if result.department in DEPARTMENT_KEYS else DEPARTMENT_KEYS[0]
    return {
        "department": dept,
        "target_email": EMAIL_ADDRESSES[dept],
        "reasoning": result.reasoning,
    }


def route_to_department(state: HRState) -> str:
    return f"handle_{state.department}"


def rag_lookup(state: HRState):
    """Run the RAG agent to find relevant HR documents for this query."""
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
    return {
        "rag_answer": rag_result.get("answer", ""),
        "rag_sources": rag_result.get("source_docs", []),
        "rag_escalation": escalation,
    }


def _make_handler(department: str):
    def handler(state: HRState):
        dept_info = DEPARTMENTS[department]
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
                f"{state.rag_answer}\n\n"
                f"Sources:\n{sources}\n"
            )

        prompt = (
            f"{dept_info['system_prompt']} Write a professional email response to "
            f"this query from {sender}.\n\n"
            f"Query: {state.query}\n"
            f"{rag_context}\n"
            f"Ground your response in the retrieved policy information above. "
            f"Cite specific document codes where applicable.\n\n"
            f"Sign off as '{dept_info['sign_off']}'."
        )
        response_body = model.invoke(prompt).content

        email_status = forward_to_department(
            department=department,
            sender_email=state.sender_email,
            query=state.query,
            response_body=response_body,
            subject=state.subject,
            message_id=state.message_id,
        )
        return {"response": response_body, "email_status": email_status}

    handler.__name__ = f"handle_{department}"
    return handler


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
