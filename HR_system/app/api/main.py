from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import EMAIL_ADDRESSES
from app.db.database import init_db, get_db, Employee, Department
from app.agents.graph import workflow
from app.agents.rag_agent import ask_hr


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="HR Email Routing System", lifespan=lifespan)


# ---- Pydantic schemas ----

class EmailRequest(BaseModel):
    sender_email: str
    query: str


class EmailResponse(BaseModel):
    sender_email: str
    routed_from: str
    routed_to: str
    department: str
    reasoning: str
    response: str
    employee_name: Optional[str] = None
    employee_id: Optional[str] = None
    email_status: Optional[dict] = None


class EmployeeOut(BaseModel):
    employee_id: str
    name: str
    email: str
    grade: str
    is_manager: bool
    country: str
    department: str

    model_config = {"from_attributes": True}


class DepartmentOut(BaseModel):
    id: int
    name: str
    employee_count: int


# ---- Email routing ----

@app.post("/send", response_model=EmailResponse)
async def route_email(request: EmailRequest):
    result = workflow.invoke({
        "query": request.query,
        "sender_email": request.sender_email,
    })
    return EmailResponse(
        sender_email=request.sender_email,
        routed_from=EMAIL_ADDRESSES["main"],
        routed_to=result["target_email"],
        department=result["department"],
        reasoning=result["reasoning"],
        response=result["response"],
        employee_name=result.get("employee_name"),
        employee_id=result.get("employee_id"),
        email_status=result.get("email_status"),
    )


# ---- RAG query ----

class AskRequest(BaseModel):
    query: str
    country: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = []
    needs_escalation: bool = False
    escalation_email: Optional[str] = None
    escalation_department: Optional[str] = None
    escalation_reason: Optional[str] = None


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    result = ask_hr(query=request.query, sender_country=request.country)
    return AskResponse(
        answer=result.get("answer", ""),
        sources=result.get("source_docs", []),
        needs_escalation=result.get("needs_escalation", False),
        escalation_email=result.get("escalation_email"),
        escalation_department=result.get("escalation_department"),
        escalation_reason=result.get("escalation_reason"),
    )


# ---- Employee endpoints ----

@app.get("/employees", response_model=list[EmployeeOut])
async def list_employees(
    department: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    is_manager: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Employee)
    if department:
        q = q.join(Department).filter(Department.name == department)
    if country:
        q = q.filter(Employee.country == country)
    if is_manager is not None:
        q = q.filter(Employee.is_manager == is_manager)
    employees = q.all()
    return [e.to_dict() for e in employees]


@app.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: str, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp.to_dict()


# ---- Department endpoints ----

@app.get("/departments", response_model=list[DepartmentOut])
async def list_departments(db: Session = Depends(get_db)):
    depts = db.query(Department).all()
    return [
        {"id": d.id, "name": d.name, "employee_count": len(d.employees)}
        for d in depts
    ]


@app.get("/emails")
async def list_emails():
    return EMAIL_ADDRESSES


@app.get("/health")
async def health():
    return {"status": "healthy"}
