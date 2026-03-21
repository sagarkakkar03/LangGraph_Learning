from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import Optional
from langchain_openai import ChatOpenAI
from enum import Enum

from config import (
    OPENAI_MODEL,
    EMAIL_ADDRESSES,
    DEPARTMENTS,
    DEPARTMENT_KEYS,
    CLASSIFIER_PROMPT_TEMPLATE,
    HANDLER_PROMPT_TEMPLATE,
)
from email_service import forward_to_department

model = ChatOpenAI(model=OPENAI_MODEL)

DepartmentEnum = Enum("DepartmentEnum", {k: k for k in DEPARTMENT_KEYS})


class DepartmentClassification(BaseModel):
    department: str = Field(
        description="The department this query should be routed to. "
        f"Must be one of: {', '.join(DEPARTMENT_KEYS)}"
    )
    reasoning: str = Field(description="Brief reasoning for the classification")


class HRState(BaseModel):
    query: str
    sender_email: str = ""
    department: Optional[str] = None
    target_email: Optional[str] = None
    response: Optional[str] = None
    reasoning: Optional[str] = None
    email_status: Optional[dict] = None


classifier = model.with_structured_output(DepartmentClassification)


def classify_query(state: HRState):
    prompt = CLASSIFIER_PROMPT_TEMPLATE.format(query=state.query)
    result = classifier.invoke(prompt)
    dept = result.department if result.department in DEPARTMENT_KEYS else DEPARTMENT_KEYS[0]
    return {
        "department": dept,
        "target_email": EMAIL_ADDRESSES[dept],
        "reasoning": result.reasoning,
    }


def route_to_department(state: HRState) -> str:
    return f"handle_{state.department}"


def _make_handler(department: str):
    def handler(state: HRState):
        dept_info = DEPARTMENTS[department]
        prompt = HANDLER_PROMPT_TEMPLATE.format(
            system_prompt=dept_info["system_prompt"],
            sender=state.sender_email or "an employee",
            query=state.query,
            sign_off=dept_info["sign_off"],
        )
        response_body = model.invoke(prompt).content

        email_status = forward_to_department(
            department=department,
            sender_email=state.sender_email,
            query=state.query,
            response_body=response_body,
        )
        return {"response": response_body, "email_status": email_status}

    handler.__name__ = f"handle_{department}"
    return handler


graph = StateGraph(HRState)
graph.add_node("classify_query", classify_query)

handler_names = []
for dept_key in DEPARTMENT_KEYS:
    node_name = f"handle_{dept_key}"
    graph.add_node(node_name, _make_handler(dept_key))
    graph.add_edge(node_name, END)
    handler_names.append(node_name)

graph.add_edge(START, "classify_query")
graph.add_conditional_edges("classify_query", route_to_department, handler_names)

workflow = graph.compile()
