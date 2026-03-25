from datetime import datetime
from typing import Any
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# ------------------------------------------------------------------ #
#  Employees
# ------------------------------------------------------------------ #

class Department(Base):
    __tablename__ = "departments"

    id = Column[int](Integer, primary_key=True, index=True)
    name = Column[str](String(100), unique=True, nullable=False)

    employees = relationship("Employee", back_populates="department")

    def __repr__(self):
        return f"<Department {self.name}>"


class Employee(Base):
    __tablename__ = "employees"

    id = Column[int](Integer, primary_key=True, index=True)
    employee_id = Column[str](String(10), unique=True, nullable=False, index=True)
    name = Column[str](String(150), nullable=False)
    email = Column[str](String(200), unique=True, nullable=False, index=True)
    grade = Column[str](String(10), nullable=False)
    is_manager = Column[bool](Boolean, default=False)
    country = Column[str](String(50), nullable=False, default="India")
    department_id = Column[int](Integer, ForeignKey("departments.id"), nullable=False)

    department = relationship("Department", back_populates="employees")

    def __repr__(self):
        return f"<Employee {self.employee_id} - {self.name}>"

    def to_dict(self):
        return {
            "employee_id": self.employee_id,
            "name": self.name,
            "email": self.email,
            "grade": self.grade,
            "is_manager": self.is_manager,
            "country": self.country,
            "department": self.department.name,
        }


# ------------------------------------------------------------------ #
#  HR Documents  (optimised for RAG + escalation)
# ------------------------------------------------------------------ #

class HRDocument(Base):
    """
    One row per HR policy / guide / career-architecture document.

    Dropped from CSV (zero-variance or redundant):
        record_id, country_group, region_scope, language,
        is_localized, version, zip_internal_path, source_zip,
        filename_is_exact

    Renamed for clarity:
        localized_code  → doc_code
        owner_channel   → escalation_email
        mailbox_function→ escalation_department
        filename        → file_path

    Added for RAG:
        content_text, content_summary, tags (ARRAY), metadata (JSONB)
    """
    __tablename__ = "hr_documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_code = Column(String(20), unique=True, nullable=False, index=True)
    base_code = Column(String(20), nullable=False, index=True)
    country_code = Column(String(5), nullable=False, index=True)
    country = Column(String(60), nullable=False)
    title = Column(String(300), nullable=False)
    doc_type = Column(String(50), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    document_family = Column(String(60), nullable=False, index=True)
    role_family = Column(String(100), nullable=True)

    escalation_email = Column(String(200), nullable=False)
    escalation_department = Column(String(60), nullable=False)

    file_path = Column(String(500), nullable=False)
    document_url = Column(String(500), nullable=True)
    related_docs = Column(ARRAY(String), default=[])
    keywords = Column(Text, nullable=True)

    content_text = Column(Text, nullable=True)
    content_summary = Column(Text, nullable=True)
    tags = Column(ARRAY(String), default=[])
    doc_metadata = Column(JSONB, default={})

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    chunks = relationship(
        "HRDocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_hrdoc_country_category", "country_code", "category"),
        Index("ix_hrdoc_family_type", "document_family", "doc_type"),
    )

    def __repr__(self):
        return f"<HRDocument {self.doc_code} - {self.title}>"

    def to_dict(self):
        return {
            "doc_code": self.doc_code,
            "base_code": self.base_code,
            "country_code": self.country_code,
            "country": self.country,
            "title": self.title,
            "doc_type": self.doc_type,
            "category": self.category,
            "document_family": self.document_family,
            "role_family": self.role_family,
            "escalation_email": self.escalation_email,
            "escalation_department": self.escalation_department,
            "file_path": self.file_path,
            "related_docs": self.related_docs,
            "keywords": self.keywords,
            "tags": self.tags,
            "is_active": self.is_active,
        }


class HRDocumentChunk(Base):
    """
    Chunked text from an HR document — the unit a RAG retriever searches over.
    Each chunk links back to its parent document for metadata / escalation info.
    """
    __tablename__ = "hr_document_chunks"

    id = Column[int](Integer, primary_key=True, index=True)
    document_id = Column[int](Integer, ForeignKey("hr_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column[int](Integer, nullable=False)
    chunk_text = Column[str](Text, nullable=False)
    section_heading = Column[str](String(300), nullable=True)
    token_count = Column[int](Integer, nullable=True)
    chunk_metadata = Column[Any](JSONB, default={})
    created_at = Column[datetime](DateTime, server_default=func.now())

    document = relationship("HRDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunk_doc_idx", "document_id", "chunk_index"),
    )

    def __repr__(self):
        return f"<Chunk {self.document_id}:{self.chunk_index}>"


class HREscalationRule(Base):
    """
    Lookup table the RAG agent uses to decide who to escalate to
    based on category, country, and sensitivity level.
    """
    __tablename__ = "hr_escalation_rules"

    id = Column[int](Integer, primary_key=True, index=True)
    category = Column[str](String(100), nullable=False)
    country_code = Column[str](String(5), nullable=True)
    sensitivity = Column[str](String(20), nullable=False, default="standard")
    escalation_email = Column[str](String(200), nullable=False)
    escalation_department = Column[str](String(60), nullable=False)
    auto_escalate = Column[bool](Boolean, default=False)
    notes = Column[str](Text, nullable=True)

    __table_args__ = (
        Index("ix_esc_cat_country", "category", "country_code"),
    )


# ------------------------------------------------------------------ #

def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
