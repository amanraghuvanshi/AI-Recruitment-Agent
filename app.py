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
    "frontend_engineer":"""
        Required Skills:
        - React/Vue.js/Angular
        - HTML5, CSS3, JavaScript/TypeScript
        - Responsive Design
        - State Management
        - Frontend Testing
    """,
    "backend_engineer": """
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
        if api_key: st.session_state.openai_api_key = api_key
        
        # Zoom Settings
        st.subheader("Zoom Configurations")
        zoom_account_id = st.text_input("Zoom Account ID", type="password", value=st.session_state.zoom_account_id)
        
        zoom_client_id = st.text_input("Zoom Client ID", type="password", value=st.session_state.zoom_client_id)
        
        zoom_client_secret = st.text_input("Zoom Client Secret", type="password", value=st.session_state.zoom_client_secret)
        
        # Email Settings
        email_sender = st.text_input("Sender Email", value=st.session_state.email_sender, help="Email address to send from")
        
        email_passkey = st.text_input("Enter Email App Password", value=st.session_state.email_passkey, type="password", help="App-specific password for email")
        
        company_name = st.text_input("Company Name", value=st.session_state.company_name, help = "Name to use in email communications")
        
        if zoom_account_id: st.session_state.zoom_account_id = zoom_account_id
        if zoom_client_id: st.session_state.zoom_client_id = zoom_client_id
        if zoom_client_secret: st.session_state.zoom_client_secret = zoom_client_secret
        
        if email_sender: st.session_state.email_sender = email_sender
        if email_passkey: st.session_state.email_passkey = email_passkey
        if company_name: st.session_state.company_name = company_name
        
        required_configs = {
            "OpenAI API Key": st.session_state.openai_api_key, 
            "Zoom Account ID": st.session_state.zoom_account_id,
            "Zoom Client ID": st.session_state.zoom_client_id,
            "Zoom Client Secret": st.session_state.zoom_client_secret,
            "Email Sender": st.session_state.email_sender, 
            "Email Password": st.session_state.email_passkey,
            "Company Name": st.session_state.company_name
        }
        
    missing_config = [k for k, v in required_configs.items() if not v]
    if missing_config:
        st.warning(f"Pleas configure the following in the sidebar: {', '.join(missing_config)}")
        return
    if not st.session_state.openai_api_key:
        st.warning("Please enter your OpenAI API Key in the sidebar to continue")
        return
    
    role = st.selectbox("Select the role you're applying for: ", ["ai_ml_engineer", "frontend_engineer", "backend_engineer"])
    
    with st.expander("View Required Skills", expanded = True): st.markdown(ROLE_REQUIREMENTS[role])
    
    # Add a "New Application" button before the resume upload
    if st.button("New Application 🔍"):
        # Clear all the application related status
        keys_to_clear = ["resume_text", "analysis_complete", "is_selected", "candidate_email", "current_pdf"]
        
        for key in keys_to_clear:
            if key in st.session_state:
                st.session_state[key] = None if key == "current_pdf" else ""
        st.rerun()
    
    resume_file = st.file_uploader("Upload your resume (PDF)", type = ["pdf"], key = "resume_uploaded")
    
    if resume_file is not None and resume_file != st.session_state.get("current_pdf"):
        st.session_state.current_pdf = resume_file
        st.session_state.resume_text = ""
        st.session_state.analysis_complete = False
        st.session_state.is_selected = False
        st.rerun()
    
    if resume_file:
        st.subheader("Uploaded Resume")
        col1, col2 = st.columns([4, 1])
        
        with col1:
            import tempfile, os
            with tempfile.NamedTemporaryFile(delete = False, suffix=".pdf") as tmp_file:
                tmp_file.write(resume_file.read())
                tmp_file_path = tmp_file.name
            resume_file.seek(0)
            try:
                pdf_viewer(tmp_file_path)
            finally:
                os.unlink(tmp_file_path)
        with col2:
            st.download_button(label="Download", 
                               data = resume_file,
                               file_name=resume_file.name, 
                               mime="application/pdf")
        # Process the resume text
        if not st.session_state.resume_text:
            with st.spinner("Processing your resume..."):
                resume_text = extract_text_from_pdf(resume_file)
                if resume_text:
                    st.session_state.resume_text = resume_text
                    st.success("Resume Processed Successfully!")
                else:
                    st.error("Could not process the PDF. Please try again")
    
    # Email input with session state
    email = st.text_input(
        "Candidate's Email Address",
        value=st.session_state.candidate_email,
        key = "email_input"
    )           
    
    st.session_state.candidate_email = email    
    
    # Analysis and next steps
    if st.session_state.resume_text and email and not st.session_state.analysis_complete:
        if st.button("Analyze Resume"):
            with st.spinner("Analyzing the resume..."):
                resume_analyzer = create_resume_analyzer()
                email_agent = create_email_agent()
                
                if resume_analyzer and email_agent:
                    print("DEBUG: Starting Resume Analysis")
                    is_selected, feedback = analyze_resume(
                        st.session_state.resume_text,
                        role, 
                        resume_analyzer
                    )
                print(f"DEBUG: Analysis Complete\n----------\nSelected: {is_selected}\nFeedback: {feedback}")
                
                if is_selected:
                    st.success("Congratulations! Your skills match our requirements.")
                    st.session_state.analysis_complete = True
                    st.session_state.is_selected = True
                    st.rerun()
                else:
                    st.warning("Your skillset are amazing, but unfortunately we have to move forward with other candidates as it doesn't match our requirements")
                    st.write(f"Feedback: {feedback}")
                    
                    # Send Rejection mail
                    with st.spinner("Sending Feedback Mail.."):
                        try:
                            send_rejection_email(
                            email_agent = email_agent,
                            to_mail = email,
                            role = role, 
                            feedback = feedback
                            )
                            st.info("We've sent you a email with detailed feedback.")
                        except Exception as e:
                            logger.error(f"Error sending rejection mail: {str(e)}")
                            st.error("Could not send the email. Please try again.")
    
    if st.session_state.get('analysis_complete') and st.session_state.get('is_selected', False):
        st.success("Congratulations! Your skills match our requirements.")
        st.info("Click 'Proceed with Application' to continue with the interview process.")
        
        if st.button("Proceed with Application", key="proceed_button"):
            print("DEBUG: Proceed button clicked")  # Debug
            with st.spinner("🔄 Processing your application..."):
                try:
                    print("DEBUG: Creating email agent")  # Debug
                    email_agent = create_email_agent()
                    print(f"DEBUG: Email agent created: {email_agent}")  # Debug
                    
                    print("DEBUG: Creating scheduler agent")  # Debug
                    scheduler_agent = create_scheduler_agent()
                    print(f"DEBUG: Scheduler agent created: {scheduler_agent}")  # Debug

                    # 3. Send selection email
                    with st.status("📧 Sending confirmation email...", expanded=True) as status:
                        print(f"DEBUG: Attempting to send email to {st.session_state.candidate_email}")  # Debug
                        send_selection_email(
                            email_agent,
                            st.session_state.candidate_email,
                            role
                        )
                        print("DEBUG: Email sent successfully")  # Debug
                        status.update(label="✅ Confirmation email sent!")

                    # 4. Schedule interview
                    with st.status("📅 Scheduling interview...", expanded=True) as status:
                        print("DEBUG: Attempting to schedule interview")  # Debug
                        schedule_interview(
                            scheduler_agent,
                            st.session_state.candidate_email,
                            email_agent,
                            role
                        )
                        print("DEBUG: Interview scheduled successfully")  # Debug
                        status.update(label="✅ Interview scheduled!")

                    print("DEBUG: All processes completed successfully")  # Debug
                    st.success("""
                        🎉 Application Successfully Processed!
                        
                        Please check your email for:
                        1. Selection confirmation ✅
                        2. Interview details with Zoom link 🔗
                        
                        Next steps:
                        1. Review the role requirements
                        2. Prepare for your technical interview
                        3. Join the interview 5 minutes early
                    """)

                except Exception as e:
                    print(f"DEBUG: Error occurred: {str(e)}")  # Debug
                    print(f"DEBUG: Error type: {type(e)}")  # Debug
                    import traceback
                    print(f"DEBUG: Full traceback: {traceback.format_exc()}")  # Debug
                    st.error(f"An error occurred: {str(e)}")
                    st.error("Please try again or contact support.")

    # Reset button
    if st.sidebar.button("Reset Application"):
        for key in st.session_state.keys():
            if key != 'openai_api_key':
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()