#!/usr/bin/env python3
"""
Streamlit App Entry Point for Vercel Deployment
Reddit Scraper Web Interface
"""

import streamlit as st
import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Streamlit for deployment
st.set_page_config(
    page_title="Reddit Scraper Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import and run the main app
from web_frontend import main
main()
