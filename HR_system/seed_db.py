"""
Seed the full Postgres database:
  1. Employees + Departments  (from employee_data.csv)
  2. HR Documents + Escalation Rules  (from hr_document_data.csv)

Usage:
    python seed_db.py
"""

import csv
import os

from database import init_db, SessionLocal, Department, Employee

CSV_PATH = os.path.join(os.path.dirname(__file__), "employee_data.csv")


def seed_employees():
    db = SessionLocal()
    try:
        if db.query(Employee).count() > 0:
            print("Employees already seeded. Skipping.")
            return

        dept_cache: dict[str, Department] = {}

        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dept_name = row["employee_department"].strip()

                if dept_name not in dept_cache:
                    dept = db.query(Department).filter_by(name=dept_name).first()
                    if not dept:
                        dept = Department(name=dept_name)
                        db.add(dept)
                        db.flush()
                    dept_cache[dept_name] = dept

                employee = Employee(
                    employee_id=row["employee_id"].strip(),
                    name=row["employee_name"].strip(),
                    email=row["employee_email"].strip(),
                    grade=row["employee_grade"].strip(),
                    is_manager=row["is_manager"].strip().lower() == "yes",
                    country=row["country"].strip(),
                    department_id=dept_cache[dept_name].id,
                )
                db.add(employee)

        db.commit()
        emp_count = db.query(Employee).count()
        dept_count = db.query(Department).count()
        print(f"Seeded {emp_count} employees across {dept_count} departments.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding employees: {e}")
        raise
    finally:
        db.close()


def seed_all():
    from seed_documents import seed_documents

    init_db()
    print("--- Seeding employees ---")
    seed_employees()
    print("--- Seeding HR documents ---")
    seed_documents()
    print("--- Done ---")


if __name__ == "__main__":
    seed_all()
