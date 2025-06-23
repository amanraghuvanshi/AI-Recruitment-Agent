import os
import json
import time
import pytz
import PyPDF2
import requests
import streamlit as st
from agno.agent import Agent
from agno.tools.email import EmailTools
from datetime import datetime, timedelta
from agno.models.openai import OpenAIChat
from typing import Literal, Tuple, Dict, Optional