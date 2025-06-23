# AI Recruitment Agent

A Streamlit-based application designed to simulate a full-service recruitment team through a suite of collaborative AI agents. These agents specialize in various stages of the hiring process—from resume screening and candidate evaluation to professional communication and interview coordination—working in unison to automate and optimize recruitment workflows.

---

## 🚀 Key Features

### 🤖 Specialized AI Agents

* **Technical Recruiter Agent**: Assesses resumes and evaluates technical competencies.
* **Communication Agent**: Manages professional candidate correspondence via email.
* **Scheduling Agent**: Coordinates interview scheduling across time zones.
* All agents operate collaboratively to deliver a holistic recruitment experience.

### 🔄 End-to-End Automation

* Intelligent resume screening and analysis.
* Tailored technical skill evaluation for each role.
* Automated and professional email communication.
* Smart interview scheduling with calendar integration.
* Feedback and status updates for both recruiters and candidates.

---

## 🔧 Pre-Setup Instructions

Before launching the app, follow these essential setup steps:

### 📧 Gmail Configuration

1. Use a dedicated Gmail account for recruitment purposes.
2. Enable 2-Step Verification on the account.
3. Generate a 16-character App Password here: [Generate App Password](https://support.google.com/accounts/answer/185833?hl=en)
   *(Use the code without spaces, e.g., `afecwejfawojfwrv`)*

### 🎥 Zoom API Configuration

1. Sign in to the [Zoom App Marketplace](https://marketplace.zoom.us).
2. Navigate to the Developer Dashboard and create a new **Server-to-Server OAuth** app.
3. Obtain the following credentials:

   * Client ID
   * Client Secret
   * Account ID
4. Add the following scopes:

   ```
   meeting:write:invite_links:admin
   meeting:write:meeting:admin
   meeting:write:meeting:master
   meeting:write:invite_links:master
   meeting:write:open_app:admin
   user:read:email:admin
   user:read:list_users:admin
   billing:read:user_entitlement:admin  *(optional)*
   dashboard:read:list_meeting_participants:admin  *(optional)*
   ```

---

## 🧪 Running the Application

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/amanraghuvanshi/AI-Recruitment-Agent-.git
cd advanced_ai_agents/multi_agent_apps/agent_teams/ai_recruitment_agent_team

# Install required packages
pip install -r requirements.txt
```

### 2. Configure API Keys

* OpenAI API Key (GPT-4o)
* Zoom API Credentials (Client ID, Client Secret, Account ID)
* Gmail App Password for recruiter email

### 3. Launch the App

```bash
streamlit run ai_recruitment_agent_team.py
```

---

## 🧠 System Architecture

### 📄 Resume Analyzer Agent

* Matches skills against job requirements
* Verifies experience and background
* Conducts preliminary technical evaluation
* Aids in shortlisting candidates

### 📧 Email Communication Agent

* Crafts professional emails automatically
* Sends notifications and updates
* Handles follow-ups and feedback sharing

### 📅 Interview Scheduler Agent

* Creates and manages Zoom meeting links
* Integrates with calendar APIs
* Adjusts for time zones
* Sends timely reminders

---

## 👤 Candidate-Centric Experience

* Easy-to-use resume upload interface
* Real-time status updates
* Transparent communication process
* Efficient and seamless interaction

---

## 🛠 Tech Stack

* **Framework**: Phidata
* **LLM Model**: OpenAI GPT-4o
* **APIs**: Zoom, Gmail (via EmailTools from Phidata)
* **Resume Parsing**: PyPDF2
* **Time Management**: pytz
* **UI State**: Streamlit Session State

---

## ⚠️ Disclaimer

This application is intended to assist and enhance the recruitment process. Automated decisions should always be reviewed and validated by human recruiters before finalizing any hiring decision.

---

## 🔮 Future Roadmap

* Integration with Applicant Tracking Systems (ATS)
* More advanced and customizable candidate scoring models
* Support for video interviews and recording
* Embedded technical and behavioral assessments
* Multi-language support for global recruitment

---
