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
        
    def get_access_token(self) -> str:
        if self.access_token and time.time() < self.token_expires_at:
            return str(self.access_token)
            
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "account_credentials", 
            "account_id": self.account_id
            }