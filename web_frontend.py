#!/usr/bin/env python3
"""
Reddit Scraper Web Frontend
A user-friendly web interface for the Reddit Keyword Scraper
"""

import streamlit as st
import pandas as pd
import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# Add current directory to Python path
sys.path.append(os.path.dirname(__file__))

# Import our Reddit scraper
from reddit_scraper import RedditScraper
from config.config import *

# Page configuration
st.set_page_config(
    page_title="Reddit Keyword Scraper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #FF4B4B;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #0068C9;
        margin-bottom: 1rem;
    }
    .metric-container {
        background-color: #F0F2F6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #D4EDDA;
        border: 1px solid #C3E6CB;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #D1ECF1;
        border: 1px solid #BEE5EB;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'search_complete' not in st.session_state:
        st.session_state.search_complete = False
    if 'excel_file_path' not in st.session_state:
        st.session_state.excel_file_path = None
    if 'search_stats' not in st.session_state:
        st.session_state.search_stats = None

def validate_reddit_credentials():
    """Check if Reddit API credentials are configured"""
    from dotenv import load_dotenv
    load_dotenv()
    
    client_id = os.getenv('REDDIT_CLIENT_ID')
    client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    user_agent = os.getenv('REDDIT_USER_AGENT')
    
    return all([client_id, client_secret, user_agent])

def create_download_button(file_path: str):
    """Create a download button for the Excel file"""
    if file_path and os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        filename = os.path.basename(file_path)
        st.download_button(
            label="📥 Download Excel Results",
            data=file_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_excel"
        )
        return True
    return False

def create_visualizations(results: List[Dict]):
    """Create visualizations for the search results"""
    if not results:
        return
    
    df = pd.DataFrame(results)
    
    # Create tabs for different visualizations
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "😊 Sentiment", "🚀 Engagement", "📈 Trends"])
    
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Posts", len(results))
        
        with col2:
            avg_score = df['Score'].mean() if 'Score' in df.columns else 0
            st.metric("Avg Reddit Score", f"{avg_score:.1f}")
        
        with col3:
            total_comments = df['Comments_Count'].sum() if 'Comments_Count' in df.columns else 0
            st.metric("Total Comments", f"{total_comments:,}")
        
        with col4:
            unique_communities = df['Community'].nunique() if 'Community' in df.columns else 0
            st.metric("Communities", unique_communities)
    
    with tab2:
        if 'Sentiment' in df.columns:
            # Sentiment distribution
            sentiment_counts = df['Sentiment'].value_counts()
            fig = px.pie(values=sentiment_counts.values, names=sentiment_counts.index,
                        title="Sentiment Distribution")
            st.plotly_chart(fig, width='stretch')
            
            # Sentiment over time if we have date data
            if 'Date' in df.columns:
                df['Date_parsed'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
                sentiment_timeline = df.groupby(['Date_parsed', 'Sentiment']).size().unstack(fill_value=0)
                fig = px.area(sentiment_timeline, title="Sentiment Trends Over Time")
                st.plotly_chart(fig, width='stretch')
    
    with tab3:
        if 'Engagement_Rate' in df.columns:
            # Top engaging posts
            top_engaging = df.nlargest(10, 'Engagement_Rate')[['Title', 'Engagement_Rate', 'Score', 'Comments_Count']]
            st.subheader("🔥 Most Engaging Posts")
            st.dataframe(top_engaging, width='stretch')
            
            # Engagement vs Score scatter plot
            fig = px.scatter(df, x='Score', y='Engagement_Rate', 
                           hover_data=['Title', 'Community'],
                           title="Engagement Rate vs Reddit Score")
            st.plotly_chart(fig, width='stretch')
    
    with tab4:
        if 'Community' in df.columns:
            # Top communities
            community_counts = df['Community'].value_counts().head(10)
            fig = px.bar(x=community_counts.values, y=community_counts.index,
                        orientation='h', title="Top Communities by Post Count")
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, width='stretch')

def main():
    """Main application function"""
    initialize_session_state()
    
    # Header
    st.markdown('<h1 class="main-header">🔍 Reddit Keyword Scraper</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">Advanced Reddit data mining with sentiment analysis, engagement metrics, and comprehensive filtering</p>', unsafe_allow_html=True)
    
    # Check Reddit credentials
    if not validate_reddit_credentials():
        st.error("⚠️ Reddit API credentials not found! Please configure your .env file with Reddit API credentials.")
        st.info("📋 Required credentials: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT")
        st.stop()
    
    # Sidebar for search parameters
    with st.sidebar:
        st.markdown('<h2 class="sub-header">🎛️ Search Parameters</h2>', unsafe_allow_html=True)
        
        # Keywords input
        st.subheader("🔤 Keywords")
        keywords_input = st.text_area(
            "Enter keywords (one per line):",
            value="Python\nartificial intelligence\nmachine learning",
            help="Enter each keyword on a new line. The scraper will search for posts containing ANY of these keywords."
        )
        keywords = [k.strip() for k in keywords_input.split('\n') if k.strip()]
        
        # Basic parameters
        st.subheader("⚙️ Basic Settings")
        
        max_results = st.slider("Max Results", min_value=10, max_value=1000, value=50, step=10)
        
        sort_method = st.selectbox(
            "Sort Method",
            options=["relevance", "hot", "new", "top", "comments"],
            help="Relevance uses Reddit search API, others crawl through posts manually"
        )
        
        subreddit = st.text_input("Subreddit", value="all", help="Enter 'all' for all subreddits or specific subreddit name")
        
        # Advanced filters
        with st.expander("🔍 Advanced Filters"):
            days_back = st.slider("Days Back (0 = all time)", min_value=0, max_value=365, value=0)
            min_score = st.slider("Minimum Reddit Score", min_value=0, max_value=100, value=0)
            min_comments = st.slider("Minimum Comments", min_value=0, max_value=50, value=0)
            min_engagement = st.slider("Minimum Engagement Rate", min_value=0.0, max_value=20.0, value=0.0, step=0.5)
            
            exclude_spam = st.checkbox("Exclude Spam Posts", value=True)
            
            sentiment_filter = st.selectbox(
                "Sentiment Filter",
                options=["all", "positive", "negative", "neutral"]
            )
        
        # Search button
        search_button = st.button("🚀 Start Search", type="primary", use_container_width=True)
    
    # Main content area
    if search_button:
        if not keywords:
            st.error("Please enter at least one keyword!")
            return
        
        # Reset previous results
        st.session_state.search_complete = False
        st.session_state.search_results = None
        st.session_state.excel_file_path = None
        
        # Create progress indicators
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Search parameters summary
        with st.expander("🔍 Search Configuration", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Keywords:** {', '.join(keywords)}")
                st.write(f"**Max Results:** {max_results}")
                st.write(f"**Sort Method:** {sort_method}")
            with col2:
                st.write(f"**Subreddit:** r/{subreddit}")
                st.write(f"**Days Back:** {'All time' if days_back == 0 else f'{days_back} days'}")
                st.write(f"**Filters:** Score≥{min_score}, Comments≥{min_comments}")
        
        try:
            # Initialize scraper
            status_text.text("🔄 Initializing Reddit scraper...")
            progress_bar.progress(10)
            
            scraper = RedditScraper()
            
            # Start search
            status_text.text("🔍 Searching Reddit...")
            progress_bar.progress(30)
            
            # Build search parameters
            search_params = {
                'keywords': keywords,
                'subreddit': subreddit,
                'sort': sort_method,
                'max_results': max_results,
                'days_back': days_back if days_back > 0 else None
            }
            
            # Execute search
            results = scraper.search_reddit(**search_params)
            progress_bar.progress(70)
            
            if results:
                status_text.text("🔄 Applying filters and enhancements...")
                
                # Apply additional filters
                filtered_results = []
                for post in results:
                    # Score filter
                    if post.get('Score', 0) < min_score:
                        continue
                    
                    # Comments filter
                    if post.get('Comments_Count', 0) < min_comments:
                        continue
                    
                    # Engagement filter
                    if post.get('Engagement_Rate', 0) < min_engagement:
                        continue
                    
                    # Spam filter
                    if exclude_spam and post.get('Spam_Likelihood', '').lower() in ['medium', 'high']:
                        continue
                    
                    # Sentiment filter
                    if sentiment_filter != 'all':
                        post_sentiment = post.get('Sentiment', '').lower()
                        if post_sentiment != sentiment_filter:
                            continue
                    
                    filtered_results.append(post)
                
                progress_bar.progress(90)
                
                if filtered_results:
                    status_text.text("📊 Exporting to Excel...")
                    
                    # Export to Excel
                    excel_path = scraper.export_to_excel(filtered_results, keywords=keywords)
                    
                    progress_bar.progress(100)
                    status_text.text("✅ Search completed successfully!")
                    
                    # Store results in session state
                    st.session_state.search_results = filtered_results
                    st.session_state.search_complete = True
                    st.session_state.excel_file_path = excel_path
                    st.session_state.search_stats = {
                        'total_found': len(results),
                        'after_filtering': len(filtered_results),
                        'keywords': keywords,
                        'search_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Success message
                    st.success(f"🎉 Found {len(filtered_results)} posts (filtered from {len(results)} total results)")
                    
                else:
                    st.warning("⚠️ No posts found after applying filters. Try relaxing the filter criteria.")
            else:
                st.error("❌ No posts found. Try different keywords or search parameters.")
                
        except Exception as e:
            st.error(f"🚨 Error during search: {str(e)}")
            progress_bar.empty()
            status_text.empty()
    
    # Display results if available
    if st.session_state.search_complete and st.session_state.search_results:
        st.markdown("---")
        st.markdown('<h2 class="sub-header">📊 Search Results</h2>', unsafe_allow_html=True)
        
        # Download button
        if create_download_button(st.session_state.excel_file_path):
            st.success("📁 Excel file ready for download!")
        
        # Results summary
        stats = st.session_state.search_stats
        if stats:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Posts Found", stats['after_filtering'])
            with col2:
                st.metric("Total Crawled", stats['total_found'])
            with col3:
                filter_rate = (1 - stats['after_filtering']/stats['total_found']) * 100 if stats['total_found'] > 0 else 0
                st.metric("Filtered Out", f"{filter_rate:.1f}%")
        
        # Visualizations
        create_visualizations(st.session_state.search_results)
        
        # Data preview
        st.subheader("📋 Data Preview")
        df = pd.DataFrame(st.session_state.search_results)
        
        # Select key columns for preview
        preview_columns = ['Title', 'Community', 'Score', 'Comments_Count', 'Sentiment', 'Relevance_Score', 'Date']
        available_columns = [col for col in preview_columns if col in df.columns]
        
        if available_columns:
            st.dataframe(df[available_columns].head(20), width='stretch')
        else:
            st.dataframe(df.head(20), width='stretch')
        
        # Show full data option
        if st.checkbox("📖 Show Full Dataset"):
            st.dataframe(df, width='stretch')

if __name__ == "__main__":
    main()