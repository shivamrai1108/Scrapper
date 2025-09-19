#!/usr/bin/env python3
"""
Advanced Reddit Scraper Web Interface
Full-featured Streamlit app with analytics, sentiment analysis, and data visualization
"""

import streamlit as st
import pandas as pd
import os
import sys
import time
import json
import io
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Reddit scraper
from reddit_scraper import RedditScraper

# Configure Streamlit
st.set_page_config(
    page_title="Reddit Scraper Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import and run the optimized main app for Vercel
try:
    from streamlit_minimal import main
    main()
except ImportError:
    # Fallback: run embedded minimal interface
    exec(open('streamlit_minimal.py').read())
