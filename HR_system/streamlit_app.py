import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the workflow
from app.agents.graph import workflow

st.set_page_config(page_title="HR AI Assistant", page_icon="🤖", layout="centered")

st.title("🤖 HR Email Routing & RAG Agent")
st.markdown("Test the HR LangGraph agent. Enter an employee email and a query to see how the system routes and responds.")

# Input fields
sender_email = st.text_input("Sender Email", value="kakkarsagar03@gmail.com")
query = st.text_area("Email Query", value="What is the parental leave policy?")

if st.button("Submit Query"):
    if not sender_email or not query:
        st.warning("Please provide both email and query.")
    else:
        with st.spinner("Processing through LangGraph..."):
            try:
                # Invoke the workflow
                result = workflow.invoke({
                    "query": query,
                    "sender_email": sender_email,
                    "subject": "Streamlit Test"
                })
                
                st.success("Processing Complete!")
                
                # Display Results
                st.subheader("Agent Response")
                st.write(result.get("response", "No response generated."))
                
                st.subheader("Routing Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Routed Department", result.get("department", "N/A"))
                with col2:
                    st.metric("Target Email", result.get("target_email", "N/A"))
                    
                with st.expander("View Agent Reasoning"):
                    st.write(result.get("reasoning", "No reasoning provided."))
                    
                with st.expander("View RAG Details"):
                    st.write("**Answer:**", result.get("rag_answer", "N/A"))
                    st.write("**Sources:**", result.get("rag_sources", []))
                    st.write("**Escalation:**", result.get("rag_escalation", "None"))
                    
                with st.expander("View Full State"):
                    st.json(result)
                    
            except Exception as e:
                st.error(f"An error occurred: {e}")
