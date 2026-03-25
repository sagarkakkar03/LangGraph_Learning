import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# --------------- LangSmith Observability ---------------
# LangChain/LangGraph ONLY reads LANGCHAIN_* env vars, NOT LANGSMITH_*
os.environ["LANGCHAIN_TRACING"] = os.getenv("LANGCHAIN_TRACING", os.getenv("LANGSMITH_TRACING", "true"))
_ls_key = os.getenv("LANGCHAIN_API_KEY", os.getenv("LANGSMITH_API_KEY", ""))
if _ls_key:
    os.environ["LANGCHAIN_API_KEY"] = _ls_key
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", os.getenv("LANGSMITH_PROJECT", "hr-email-router"))

# --------------- OpenAI ---------------
OPENAI_MODEL = "gpt-5.2"
EMBEDDING_MODEL = "text-embedding-3-small"

# --------------- RAG ---------------
DOCS_DIR = os.path.join(PROJECT_ROOT, "data", "DocsHR")
FAISS_INDEX_DIR = os.path.join(PROJECT_ROOT, "data", "faiss_index")
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RAG_TOP_K = 6

# --------------- Database ---------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/hr_system",
)

# --------------- IMAP (reading inbox) ---------------
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

# --------------- SMTP (sending mail) ---------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# --------------- Department Emails ---------------
EMAIL_ADDRESSES = {
    "main": os.getenv("EMAIL_MAIN", "hr@company.com"),
    "people_team": os.getenv("EMAIL_PEOPLE_TEAM", "peopleteam@company.com"),
    "payroll": os.getenv("EMAIL_PAYROLL", "payroll@company.com"),
    "benefits": os.getenv("EMAIL_BENEFITS", "benefits@company.com"),
    "talent_development": os.getenv("EMAIL_TALENT_DEV", "talentdevelopment@company.com"),
    "onboarding": os.getenv("EMAIL_ONBOARDING", "onboarding@company.com"),
    "compliance": os.getenv("EMAIL_COMPLIANCE", "compliance@company.com"),
    "recruitment": os.getenv("EMAIL_RECRUITMENT", "recruitment@company.com"),
    "it_support": os.getenv("EMAIL_IT_SUPPORT", "itsupport@company.com"),
}

# --------------- Department Metadata ---------------
DEPARTMENTS = {
    "people_team": {
        "keywords": (
            "Employee relations, workplace culture, conflict resolution, "
            "team dynamics, employee engagement, HR policies, grievances, "
            "leave policy, parental leave, sick leave, vacation, PTO, bereavement leave"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the People Team. You handle employee relations, "
            "workplace culture, and interpersonal matters. Be empathetic, "
            "professional, and provide supportive guidance."
        ),
        "color": "#6c5ce7",
    },
    "payroll": {
        "keywords": (
            "Salary, tax, compensation, pay slips, wage queries, "
            "reimbursements, direct deposit, overtime pay"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the Payroll department. "
            "Be helpful, professional, and provide specific guidance "
            "on salary, tax, and compensation processes."
        ),
        "color": "#fdcb6e",
    },
    "benefits": {
        "keywords": (
            "Health insurance, retirement plans, 401k, wellness programs, "
            "dental, vision, life insurance, benefits enrollment, perks"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the Benefits department. "
            "Be helpful, professional, and provide clear guidance on "
            "insurance plans, retirement options, and employee perks."
        ),
        "color": "#00b894",
    },
    "talent_development": {
        "keywords": (
            "Training, career development, skill building, mentorship, "
            "performance reviews, promotions, learning programs, certifications"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the Talent Development department. "
            "Be encouraging, professional, and provide guidance on "
            "growth opportunities, training, and career paths."
        ),
        "color": "#0984e3",
    },
    "onboarding": {
        "keywords": (
            "New hire orientation, first-day logistics, welcome packages, "
            "documentation for new employees, ID badges, account setup for new joiners"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the Onboarding department. "
            "Be welcoming, professional, and guide new hires through "
            "their joining process step by step."
        ),
        "color": "#00cec9",
    },
    "compliance": {
        "keywords": (
            "Legal compliance, workplace policies, harassment reports, "
            "safety regulations, code of conduct, audits, whistleblower concerns"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the Compliance department. "
            "Be precise, professional, and handle sensitive matters "
            "with confidentiality and care."
        ),
        "color": "#d63031",
    },
    "recruitment": {
        "keywords": (
            "Job applications, interviews, hiring decisions, job postings, "
            "career opportunities, referrals, candidate status"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the Recruitment department. "
            "Be helpful, professional, and provide clear next steps."
        ),
        "color": "#e17055",
    },
    "it_support": {
        "keywords": (
            "Technical issues, software access, hardware problems, "
            "password resets, VPN, system access, equipment requests"
        ),
        "sign_off": "OMEGA",
        "system_prompt": (
            "You are OMEGA, the AI HR Assistant for the IT Support department. "
            "Be helpful, professional, and provide troubleshooting steps "
            "or next actions."
        ),
        "color": "#636e72",
    },
}

DEPARTMENT_KEYS = list(DEPARTMENTS.keys())

# Maps the escalation_department values from HR documents to our routing keys.
# The documents use "people_operations" but our department key is "people_team", etc.
DOC_ESCALATION_TO_DEPT = {
    "people_operations": "people_team",
    "benefits": "benefits",
    "compliance": "compliance",
    "it_support": "it_support",
    "onboarding": "onboarding",
    "payroll": "payroll",
    "recruitment": "recruitment",
    "talent_development": "talent_development",
}

CLASSIFIER_PROMPT_TEMPLATE = (
    "You are an HR email router. Classify the following employee query "
    "into exactly one of these departments:\n"
    + "\n".join(
        f"- {dept}: {info['keywords']}"
        for dept, info in DEPARTMENTS.items()
    )
    + "\n\nQuery: {query}"
)
HANDLER_PROMPT_TEMPLATE = (
    "{system_prompt} Write a professional email response to this query "
    "from {sender}.\n\n"
    "Query: {query}\n\n"
    "Sign off as '{sign_off}'."
)

