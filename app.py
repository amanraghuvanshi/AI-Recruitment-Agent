import os
import json
import time
import pytz
import PyPDF2
import requests
import streamlit as st

from agno.agent import Agent
from phi.utils.log import logger
from phi.tools.zoom import ZoomTool
from agno.tools.email import EmailTools
from datetime import datetime, timedelta
from agno.models.openai import OpenAIChat
from streamlit_pdf_viewer import pdf_viewer
from typing import Literal, Tuple, Dict, Optional

# Class for controlling zoom access
class CustomZoomTool(ZoomTool):
    def __init__(self, *, account_id: Optional[str] = None, client_id: Optional[str] = None,
             client_secret: Optional[str] = None, name: str = "zoom_tool"):
        super().__init__(account_id=account_id, client_id=client_id, client_secret=client_secret, name=name)
        self.token_url = "https://zoom.us/oauth/token"
        self.access_token = None
        self.token_expires_at = 0
        
# This method fetches and returns a valid Zoom access token, either from cache or by making an API call.
    def get_access_token(self) -> str:
        # If token exists and hasn't expired, return it (avoids unnecessary API calls).
        if self.access_token and time.time() < self.token_expires_at:
            return str(self.access_token)
        # Sets up headers and payload for the Zoom OAuth token request.
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "account_credentials", 
            "account_id": self.account_id
            }
        # Makes a POST request to Zoom's token endpoint using the client secret for authentication.
        try:
            resp = requests.post(
                self.token_url, 
                headers= headers, 
                data = data, 
                auth = (self.client_secret)
            )
            
            resp.raise_for_status()
            
            token_info = resp.json()
            
            self.access_token = token_info["access_token"]
            expires_in = token_info["expires_in"]
            self.token_expires_at = time.time() + expires_in + 60
            
            self._set_parent_token(str(self.access_token))
            return str(self.access_token)
        # Logs and safely handles any network or response issues.
        except requests.RequestException as e:
            logger.error(f"Error Fetching access token: {e}")
            return ""
    
    def _set_parent_token(self, token: str) -> None:
        """
        Helper Function to set the token in parent ZoomTool class
        """
        if token:
            self._ZoomTool_access_token = token
            
# ROLE Requirements as a constant dictionary

ROLE_REQUIREMENTS: Dict[str, str] = {
    "ai_ml_engineer": """
        Required Skills:
        - Python, Pytorch/Tensorflow
        - Machine Learning Algorithms and Frameworks
        - Deep Learning and Neural Networks
        - Data Preprocessing and Analysis
        - MLOps and Model Deployment
        - RAG, LLMs, Finetuning and Prompt Engineering
    """,
    "Frontend Developer / Engineer":"""
        Required Skills:
        - React/Vue.js/Angular
        - HTML5, CSS3, JavaScript/TypeScript
        - Responsive Design
        - State Management
        - Frontend Testing
    """,
    "Backend Engineer": """
        Required Skills:
        - Python/Java/Node.js
        - REST APIs
        - Database Design and Management
        - System Architecture
        - Cloud Services (AWS/GCP/Azure)
        - Kubernetes, Docker, CI/CD
    """
}

#  safely initialize only the required keys in st.session_state with default values, preventing errors during use in a Streamlit app.
def init_session_state() -> None:
    """Initialize only the necessary session state variables."""
    defaults = {
        "candidate_email": "",
        "openai_api_key" : "",
        "resume_text": "",
        "analysis_complete": False,
        "is_selected": False,
        "zoom_account_id": "",
        "zoom_client_id": "",
        "zoom_client_secret": "",
        "email_sender": "",
        "email_passkey": "",
        "company_name": "",
        "current_pdf": None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
            
# This function returns a function if the API is already initialized
def create_resume_analyzer() -> Agent:
    """Creates and returns a resume analysis agent"""
    if not st.session_state.openai_api_key:
        st.error("Please enter your OpenAI API Key before procedding!")
        return None
    return Agent(
        model = OpenAIChat(id="gpt-4.1-nano", api_key = st.session_state.openai_api_key),
        description = "You are a expert Technical Recruiter who analyzes resumes",
        instructions=[
            "Analyze the resume against the provided job requirements",
            "Be linient with AI/ML candidates who show strong potential",
            "Consider project experience as valid experience",
            "Value hands-on-experience with key technologies",
            "Return the result in a JSON response with selection decision and feedback"
        ],
        markdown=True
    )
    
def create_email_agent() -> Agent:
    return Agent(
        model = OpenAIChat(
            id = "gpt-4.1-nano",
            api_key=st.session_state.openai_api_key
        ),
        description="You are a expert technical recruiter coordinator handling email communications.",
        instructions=[
            "Draft and send professional recruitment emails",
            "Act like a huma writing an email and eliminate unnecessary capital letters",
            "Maintain a friendly yet professional tone",
            f"Always end the mail with exactly: 'Best Regards\nTeam HR at {st.session_state.company_name}",
            "Never include the sender's or receiver's name in the signature",
            f"The name of the company is {st.session_state.company_name}"
        ],
        markdown=True, 
        show_tool_calls=True
    )

def create_scheduler_agent() -> Agent:
    zoom_tools = CustomZoomTool(
        account_id = st.session_state.zoom_accound_id,
        client_id = st.session_state.zoom_client_id,
        client_secret = st.session_state.zoom_client_secret
    )
    
    return Agent(
        name = "Interview Scheduler",
        model = OpenAIChat(
            id = "gpt-4o-mini",
            api_key = st.session_state.openai_api_key
        ),
        tools = [zoom_tools],
        description = "You are an interview scheduling coordinator",
        instructions = [
            "You are an expert at scheduling technical interviews using zoom",
            "Schedule interviews during business hours (9AM - 5PM IST)",
            "Create meetings with proper titles and descriptions",
            "Ensure all meeting details are included in responses",
            "Use ISO 8601 format for dates",
            "Handle scheduling errors gracefully"
        ],
        markdown=True,
        show_tool_calls=True
    )
    
def extract_text_from_pdf(pdf_file) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error while parsing PDF File: {str(e)}")
        return ""

def analyze_resume(resume_text: str, 
                   role: Literal["ai_ml_engineer", "frontend_engineer", "backend_engineer"],
                   analyzer: Agent) -> Tuple[bool, str]:
    try:
        resp = analyzer.run(
            f"""Please analyze this resume against the following requirements and provide your response in valid JSON format:
            Role Requirements:
            {ROLE_REQUIREMENTS[role]}
            Resume Text:
            {resume_text}
            
            Your response must be a valid JSON object, just like this:
            {{
                "selected":true/false,
                "feedback":"Detailed Feedback explaining decision",
                "matching_skills":["skill1", "skill2"],
                "missing_skills":["skill1", "skill2"],
                "experience_level":"junior/mid/senior"
            }}
            
            Evaluation Criteria:
            1. Match at least 70% of required skills.
            2. Consider both theoritical knowledge and pratical knowledge.
            3. Value project experience and real-world applications.
            4. Consider transferrable skills from similar technologies.
            5. Look for evidence for continuous learning and adaptability.
            Important: Return ONLY the JSON object without any formatting or backticks.
            """
        )
        
        assistant_message = next((msg.content for msg in resp.messages if msg.role == "assistant"), None)
        
        if not assistant_message:
            raise ValueError("No assistant message found in the response")
        result = json.loads(assistant_message.strip())
        if not isinstance(result, dict) or not all(k in result for k in ["selected", "feedback"]):
            raise ValueError("Invalid Response Format")
        return result["selected"], result["feedback"]
    except (json.JSONDecodeError, ValueError) as e:
        st.error(f"Error, while decoding JSON or due to format: {str(e)}")
        return False, f"Error while analyzing resume: {str(e)}"

def send_selection_email(email_agent: Agent, to_email: str, role: str) -> None:
    """
    Send a selection email with a congratuations.
    """
    email_agent.run(
        f"""
        Send an email to {to_email} regarding their selection for the {role} position.
        The email should:
        1. Congratulate them on being selected.
        2. Explain the next steps in the process.
        3. Mention that they will receive interview details shortly.
        4. The name of the company is {st.session_state.company_name}.
        """
    )

def send_rejection_email(email_agent: Agent, to_email : str, role : str, feedback : str) -> None:
    """
    Send a rejection mail with constructive feedback
    """
    email_agent.run(
        f"""
        Send an email to {to_email} regarding their application for the {role} position.
        Use this specific style:
        1. Avoid unnecessary capital letters.
        2. Be empathetic and human
        3. Mention specific feedback from: {feedback}
        4. Encourage them to upskill and try again
        5. Suggest some learning resources based on missing skills.
        6. End the email with exactly:
            Best Regards,
            Team HR at {st.session_state.company_name}
        Do not include any name in the signature.
        The tone should be like a human writing a quick but thoughtful email.
        """
    )
    
def schedule_interview(scheduler: Agent, candidate_email: str, email_agent: Agent, role: str) -> None:
    """
    Schedule interview during business hours (9 AM - 5 PM IST)
    """
    try:
        # getting the current time
        ist_tz = pytz.timezone("Asia/Kolkata")
        current_time_ist = datetime.now(ist_tz)
        
        tomorrow_ist = current_time_ist + timedelta(days=1)
        interview_time = tomorrow_ist.replace(hour=11, minute=0, second=0, microsecond=0)
        formatted_time = interview_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        meeting_resp = scheduler.run(
            f"""Schedule a 60-minute technical interview with these specifications:
                - Title: '{role} Technical Interview'
                - Date: {formatted_time}
                - Timezone: IST (Indian Standard Time)
                - Attendee: {candidate_email}
                
            Important Notes:
                - The meeting must be between 9 AM - 5 PM IST
                - Use IST (UTC+5:30) timezone for all communications
                - Include timezone information in the meeting details
                - Ask him to be confident and not so nervous and prepare well for the interview
                - Also, include a small joke or sarcasm to make him relax.
            """
        )
        
        st.success("Interview Scheduled Successfully! Check your email for details.")
    except Exception as e:
        logger.error(f"Error scheduling Interview: {str(e)}")
        st.error("Unable to schedule interview. Please try again")
        
def main() -> None:
    st.title("HeyHR Aide 🏢")
    
    init_session_state()
    
    with st.sidebar:
        st.header("Configurations")
        
        # OpenAI configurations
        st.subheader("OpenAI Configurations")
        api_key = st.text_input("OpenAI API Key", placeholder="API key here", type="password", value=st.session_state.openai_api_key, help="Get your OpenAI API Key from platform.openai.com")