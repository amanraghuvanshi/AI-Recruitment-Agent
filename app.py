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
        model = OpenAIChat("gpt-4.1-nano", api_key = st.session_state.openai_api_key),
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
    
