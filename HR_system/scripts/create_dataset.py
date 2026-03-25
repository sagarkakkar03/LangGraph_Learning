import sys, os
from dotenv import load_dotenv

# Load .env explicitly so LangSmith picks up the API key
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client

def create_dataset():
    client = Client()
    dataset_name = "HR_Email_Benchmark2"
    
    # Check if dataset exists and delete if we want to recreate it fresh
    if client.has_dataset(dataset_name=dataset_name):
        client.delete_dataset(dataset_name=dataset_name)
        
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="Benchmark dataset for HR email routing, escalation, and RAG responses."
    )
    
    # We use the email that is known to be in the DB
    test_email = "kakkarsagar03@gmail.com"
    
    examples = [
        # --- People Team ---
        {"query": "What is the parental leave policy for me?", "dept": "people_team", "escalate": False},
        {"query": "Can you tell me what the parental leave policy is for employees based in Brazil?", "dept": "people_team", "escalate": False},
        {"query": "My manager is ignoring my requests for a 1-on-1.", "dept": "people_team", "escalate": True},
        # --- Compliance ---
        {"query": "I am being harassed at workplace by my manager.", "dept": "compliance", "escalate": True},
        {"query": "I want to report a safety hazard in the office.", "dept": "compliance", "escalate": True},
        {"query": "I feel discriminated against because of my age.", "dept": "compliance", "escalate": True},
        {"query": "I witnessed a colleague stealing company property.", "dept": "compliance", "escalate": True},
        {"query": "What is the policy on accepting gifts from vendors?", "dept": "compliance", "escalate": False},

        # --- Payroll ---
        {"query": "When is the next pay date and how do I read my payslip?", "dept": "payroll", "escalate": False},
        {"query": "I didn't get paid for my overtime last week.", "dept": "payroll", "escalate": True},
        {"query": "How do I update my direct deposit information?", "dept": "payroll", "escalate": True},
        {"query": "Please update my tax withholding status.", "dept": "payroll", "escalate": True},

        # --- Benefits ---
        {"query": "I need to add my newborn to my health insurance plan. How do I do this?", "dept": "benefits", "escalate": True},
        {"query": "How do I enroll in the 401k plan?", "dept": "benefits", "escalate": True},
        {"query": "Is dental insurance covered under our standard plan?", "dept": "benefits", "escalate": False},
        {"query": "Does the company offer any mental health support or counseling?", "dept": "benefits", "escalate": False},

        # --- IT Support ---
        {"query": "My laptop is broken and I can't connect to the VPN.", "dept": "it_support", "escalate": True},
        {"query": "I need a new mouse, mine stopped working.", "dept": "it_support", "escalate": True},
        {"query": "I need help setting up my development environment.", "dept": "it_support", "escalate": True},
        {"query": "I lost my ID badge, how do I get a new one?", "dept": "it_support", "escalate": True},

        # --- Talent Development ---
        {"query": "What is the budget for the learning and development stipend?", "dept": "talent_development", "escalate": False},
        {"query": "I want to take a course on AWS. How do I get reimbursed?", "dept": "talent_development", "escalate": True},
        {"query": "What are the eligibility criteria for the tuition reimbursement program?", "dept": "talent_development", "escalate": False},

        # --- Recruitment ---
        {"query": "Can you send me the link to the internal job board?", "dept": "recruitment", "escalate": False},
        {"query": "I'd like to refer a friend for the Senior Engineer role.", "dept": "recruitment", "escalate": True},
        {"query": "What is the process for internal transfers?", "dept": "recruitment", "escalate": False},

        # --- Onboarding ---
        {"query": "I'm a new hire, when do I get my welcome package?", "dept": "onboarding", "escalate": False},
    ]
    
    formatted_examples = []
    for ex in examples:
        formatted_examples.append({
            "inputs": {
                "query": ex["query"],
                "sender_email": test_email
            },
            "outputs": {
                "expected_department": ex["dept"],
                "needs_escalation": ex["escalate"],
            }
        })
    
    client.create_examples(
        inputs=[e["inputs"] for e in formatted_examples],
        outputs=[e["outputs"] for e in formatted_examples],
        dataset_id=dataset.id
    )
    print(f"Dataset '{dataset_name}' created successfully with {len(formatted_examples)} examples.")

if __name__ == "__main__":
    create_dataset()
