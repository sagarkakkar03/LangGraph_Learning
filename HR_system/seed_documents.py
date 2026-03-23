"""
Seed hr_documents and hr_escalation_rules from hr_document_data.csv.

Usage:
    python seed_documents.py
"""

import csv
import os

from database import init_db, SessionLocal, HRDocument, HREscalationRule

CSV_PATH = os.path.join(os.path.dirname(__file__), "hr_document_data.csv")

SENSITIVITY_MAP = {
    "Compliance": "high",
    "Employee Relations": "high",
    "Offboarding": "medium",
    "Recruitment": "medium",
    "Benefits": "standard",
    "Payroll": "standard",
    "Leave Management": "standard",
    "HR Operations": "standard",
    "Onboarding": "standard",
    "IT Security": "high",
    "People Team": "standard",
    "Talent Development": "standard",
}


def _parse_related_docs(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return []
    return [code.strip() for code in raw.split(",") if code.strip()]


def _parse_tags(keywords: str, category: str, doc_type: str) -> list[str]:
    """Build a flat tag list from the pipe-separated keywords, category and doc_type."""
    tags = set()
    if keywords:
        for part in keywords.split("|"):
            tags.add(part.strip().lower())
    tags.add(category.lower())
    tags.add(doc_type.lower())
    tags.discard("")
    return sorted(tags)


def seed_documents():
    init_db()
    db = SessionLocal()

    try:
        if db.query(HRDocument).count() > 0:
            print("hr_documents already seeded. Skipping.")
            return

        escalation_seen: set[tuple[str, str | None]] = set()

        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                category = row["category"].strip()
                country_code = row["country_code"].strip()
                esc_email = row["owner_channel"].strip()
                esc_dept = row["mailbox_function"].strip()
                keywords_raw = row["keywords"].strip()
                doc_type = row["doc_type"].strip()

                doc = HRDocument(
                    doc_code=row["localized_code"].strip(),
                    base_code=row["base_code"].strip(),
                    country_code=country_code,
                    country=row["country"].strip(),
                    title=row["title"].strip(),
                    doc_type=doc_type,
                    category=category,
                    document_family=row["document_family"].strip(),
                    role_family=row.get("role_family", "").strip() or None,
                    escalation_email=esc_email,
                    escalation_department=esc_dept,
                    file_path=row["filename"].strip(),
                    related_docs=_parse_related_docs(row["related_docs"]),
                    keywords=keywords_raw,
                    tags=_parse_tags(keywords_raw, category, doc_type),
                    is_active=row["active"].strip().lower() == "true",
                )
                db.add(doc)

                esc_key = (category, country_code)
                if esc_key not in escalation_seen:
                    escalation_seen.add(esc_key)
                    rule = HREscalationRule(
                        category=category,
                        country_code=country_code,
                        sensitivity=SENSITIVITY_MAP.get(category, "standard"),
                        escalation_email=esc_email,
                        escalation_department=esc_dept,
                        auto_escalate=category in ("Compliance", "Employee Relations"),
                    )
                    db.add(rule)

        db.commit()
        doc_count = db.query(HRDocument).count()
        rule_count = db.query(HREscalationRule).count()
        print(f"Seeded {doc_count} documents and {rule_count} escalation rules.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding documents: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_documents()
