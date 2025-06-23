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
        
        
            