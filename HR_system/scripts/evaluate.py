import sys, os
from dotenv import load_dotenv

# Load .env explicitly so LangSmith picks up the API key
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client, evaluate
from app.agents.graph import workflow
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from app.core.config import OPENAI_MODEL

client = Client()

def predict(inputs: dict) -> dict:
    """Wrapper around the LangGraph workflow for evaluation."""
    # We don't want the evaluation script to actually send real emails via SMTP.
    # We just want to see what the workflow generated.
    # We can mock the forward_to_department function.
    from unittest.mock import patch
    
    with patch('app.agents.graph.forward_to_department') as mock_fwd:
        mock_fwd.return_value = {"success": True, "message": "Mocked email send"}
        
        result = workflow.invoke({
            "query": inputs["query"],
            "sender_email": inputs["sender_email"],
            "subject": "Benchmark Test Query"
        })
    
    # Extract the relevant fields for evaluation
    return {
        "department": result.get("department"),
        "needs_escalation": bool(result.get("rag_escalation")),
        "response": result.get("response", "")
    }

# --- Evaluators ---

def department_match(run, example) -> dict:
    """Check if the routed department matches the expected department."""
    expected = example.outputs["expected_department"]
    actual = run.outputs["department"]
    return {"key": "department_match", "score": int(expected == actual)}

def escalation_match(run, example) -> dict:
    """Check if the escalation decision matches the expected decision."""
    expected = example.outputs["needs_escalation"]
    actual = run.outputs["needs_escalation"]
    return {"key": "escalation_match", "score": int(expected == actual)}

class ResponseEval(BaseModel):
    score: int = Field(description="Score 1 if the response is professional, helpful, and appropriate. 0 otherwise.")
    reasoning: str = Field(description="Reasoning for the score.")

def response_quality(run, example) -> dict:
    """LLM-as-a-judge to evaluate response quality."""
    query = example.inputs["query"]
    response = run.outputs["response"]
    needs_escalation = run.outputs["needs_escalation"]
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(ResponseEval)
    
    prompt = f"""
    Evaluate the quality of this HR bot response.
    
    User Query: {query}
    Bot Response: {response}
    Was this escalated to a human? {needs_escalation}
    
    Criteria for score=1:
    - If escalated, the bot MUST acknowledge the escalation politely and NOT attempt to fully answer the policy query.
    - If not escalated, the bot MUST answer the query using plain text, cite policies, and be professional.
    - The tone must be empathetic and professional.
    - There should be NO markdown formatting (like **bold**).
    
    Score 0 if it fails any criteria.
    """
    
    eval_result = llm.invoke(prompt)
    return {"key": "response_quality", "score": eval_result.score, "comment": eval_result.reasoning}

if __name__ == "__main__":
    # Must match scripts/create_dataset.py `dataset_name` (25 examples).
    dataset_name = "HR_Email_Benchmark2"
    
    print(f"Starting evaluation on dataset: {dataset_name}")
    experiment_results = evaluate(
        predict,
        data=dataset_name,
        evaluators=[department_match, escalation_match, response_quality],
        experiment_prefix="hr-bot-eval",
        metadata={"version": "1.0"}
    )
    print("Evaluation complete! View results in LangSmith.")
