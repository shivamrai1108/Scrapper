#!/usr/bin/env python3
"""
Advanced Reddit Scraper Interface
Complete analytics dashboard with sentiment analysis, engagement metrics, and data visualization
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import json
import io
import praw
import tempfile
from textblob import TextBlob
import re

# Initialize session state
def initialize_session_state():
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'search_complete' not in st.session_state:
        st.session_state.search_complete = False
    if 'excel_data' not in st.session_state:
        st.session_state.excel_data = None

def get_reddit_instance():
    """Get Reddit API instance"""
    try:
        return praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID', '').strip(),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET', '').strip(),
            user_agent=os.getenv('REDDIT_USER_AGENT', 'RedditScraper/1.0').strip()
        )
    except Exception as e:
        st.error(f"Reddit API Error: {e}")
        return None

def analyze_sentiment(text):
    """Simple sentiment analysis using TextBlob"""
    if not text:
        return 'neutral', 0.0
    
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        
        if polarity > 0.1:
            return 'positive', polarity
        elif polarity < -0.1:
            return 'negative', polarity
        else:
            return 'neutral', polarity
    except:
        return 'neutral', 0.0

def calculate_engagement_rate(score, comments):
    """Calculate engagement rate"""
    if score <= 0:
        return 0.0
    return (comments / score) * 100

def calculate_relevance_score(post, keywords):
    """Calculate relevance score for a post"""
    score = 0
    title = post.title.lower()
    content = (post.selftext or '').lower()
    
    for keyword in keywords:
        keyword = keyword.lower()
        # Title matches get higher score
        score += title.count(keyword) * 20
        # Content matches
        score += content.count(keyword) * 10
        # Exact word boundary matches get bonus
        if re.search(r'\b' + re.escape(keyword) + r'\b', title):
            score += 15
        if re.search(r'\b' + re.escape(keyword) + r'\b', content):
            score += 5
    
    return min(score, 100)  # Cap at 100

def search_reddit(keywords, subreddit='all', sort='relevance', max_results=50, days_back=None):
    """Search Reddit with advanced filtering"""
    reddit = get_reddit_instance()
    if not reddit:
        return []
    
    results = []
    search_query = ' OR '.join(keywords)
    
    try:
        if subreddit.lower() == 'all':
            subreddit_obj = reddit.subreddit('all')
        else:
            subreddit_obj = reddit.subreddit(subreddit)
        
        # Search posts
        for post in subreddit_obj.search(search_query, sort=sort, limit=max_results):
            # Date filtering
            if days_back:
                post_date = datetime.fromtimestamp(post.created_utc)
                cutoff_date = datetime.now() - timedelta(days=days_back)
                if post_date < cutoff_date:
                    continue
            
            # Analyze sentiment
            text_to_analyze = f"{post.title} {post.selftext or ''}"
            sentiment, sentiment_score = analyze_sentiment(text_to_analyze)
            
            # Calculate metrics
            engagement_rate = calculate_engagement_rate(post.score, post.num_comments)
            relevance_score = calculate_relevance_score(post, keywords)
            
            result = {
                'Title': post.title,
                'Subreddit': str(post.subreddit),
                'Author': str(post.author) if post.author else '[deleted]',
                'Score': post.score,
                'Upvote_Ratio': post.upvote_ratio,
                'Comments_Count': post.num_comments,
                'Created_UTC': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                'Date': datetime.fromtimestamp(post.created_utc).strftime('%d-%m-%Y'),
                'URL': f"https://reddit.com{post.permalink}",
                'Content': post.selftext[:500] + '...' if len(post.selftext or '') > 500 else post.selftext or '',
                'NSFW': post.over_18,
                'Post_ID': post.id,
                'Sentiment': sentiment,
                'Sentiment_Score': sentiment_score,
                'Engagement_Rate': engagement_rate,
                'Relevance_Score': relevance_score,
                'Community': str(post.subreddit),
                'Keywords_Found': ', '.join([kw for kw in keywords if kw.lower() in post.title.lower() or kw.lower() in (post.selftext or '').lower()])
            }
            results.append(result)
    
    except Exception as e:
        st.error(f"Search error: {e}")
        return []
    
    return results

def create_excel_download(results, keywords):
    """Create Excel file for download"""
    if not results:
        return None
    
    df = pd.DataFrame(results)
    
    # Create Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main data sheet
        df.to_excel(writer, sheet_name='Reddit_Data', index=False)
        
        # Summary sheet
        summary_data = {
            'Metric': ['Total Posts', 'Unique Subreddits', 'Avg Score', 'Avg Comments', 'Positive Sentiment %', 'Negative Sentiment %'],
            'Value': [
                len(results),
                df['Subreddit'].nunique(),
                df['Score'].mean(),
                df['Comments_Count'].mean(),
                (df['Sentiment'] == 'positive').mean() * 100,
                (df['Sentiment'] == 'negative').mean() * 100
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
    
    output.seek(0)
    return output.getvalue()

def create_visualizations(results):
    """Create comprehensive data visualizations"""
    if not results:
        return
    
    df = pd.DataFrame(results)
    
    # Create tabs for different visualizations
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "😊 Sentiment", "🚀 Engagement", "📈 Trends"])
    
    with tab1:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Posts", len(results))
        with col2:
            avg_score = df['Score'].mean()
            st.metric("Avg Score", f"{avg_score:.1f}")
        with col3:
            total_comments = df['Comments_Count'].sum()
            st.metric("Total Comments", f"{total_comments:,}")
        with col4:
            unique_subs = df['Subreddit'].nunique()
            st.metric("Subreddits", unique_subs)
        
        # Score distribution
        fig = px.histogram(df, x='Score', bins=20, title='Score Distribution')
        st.plotly_chart(fig, use_container_width=True)
        
        # Top subreddits
        top_subs = df['Subreddit'].value_counts().head(10)
        fig = px.bar(x=top_subs.values, y=top_subs.index, orientation='h', 
                    title='Top Subreddits by Post Count')
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Sentiment analysis
        sentiment_counts = df['Sentiment'].value_counts()
        
        # Pie chart
        fig = px.pie(values=sentiment_counts.values, names=sentiment_counts.index,
                    title='Sentiment Distribution')
        st.plotly_chart(fig, use_container_width=True)
        
        # Sentiment by subreddit
        if len(df) > 10:
            sentiment_by_sub = df.groupby('Subreddit')['Sentiment'].value_counts().unstack(fill_value=0)
            if not sentiment_by_sub.empty:
                fig = px.bar(sentiment_by_sub, title='Sentiment by Subreddit')
                st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Engagement analysis
        fig = px.scatter(df, x='Score', y='Engagement_Rate', hover_data=['Title', 'Subreddit'],
                        title='Engagement Rate vs Score')
        st.plotly_chart(fig, use_container_width=True)
        
        # Top engaging posts
        top_engaging = df.nlargest(10, 'Engagement_Rate')[['Title', 'Engagement_Rate', 'Score', 'Comments_Count']]
        st.subheader("🔥 Most Engaging Posts")
        st.dataframe(top_engaging, use_container_width=True)
    
    with tab4:
        # Trends over time
        df['Date_parsed'] = pd.to_datetime(df['Created_UTC'])
        df['Date_only'] = df['Date_parsed'].dt.date
        
        daily_counts = df.groupby('Date_only').size()
        fig = px.line(x=daily_counts.index, y=daily_counts.values, title='Posts Over Time')
        st.plotly_chart(fig, use_container_width=True)
        
        # Relevance scores
        fig = px.histogram(df, x='Relevance_Score', bins=20, title='Relevance Score Distribution')
        st.plotly_chart(fig, use_container_width=True)

def main():
    """Main application"""
    initialize_session_state()
    
    # Header
    st.title("🔍 Reddit Scraper Pro")
    st.markdown("**Advanced Reddit data mining with sentiment analysis, engagement metrics, and comprehensive filtering**")
    
    # Sidebar
    with st.sidebar:
        st.header("🎛️ Search Parameters")
        
        # Keywords
        st.subheader("🔤 Keywords")
        keywords_input = st.text_area(
            "Enter keywords (one per line):",
            value="Python\nartificial intelligence\nmachine learning",
            help="Enter each keyword on a new line"
        )
        keywords = [k.strip() for k in keywords_input.split('\n') if k.strip()]
        
        # Basic settings
        st.subheader("⚙️ Basic Settings")
        max_results = st.slider("Max Results", min_value=10, max_value=500, value=100, step=10)
        sort_method = st.selectbox("Sort Method", ["relevance", "hot", "new", "top", "comments"])
        subreddit = st.text_input("Subreddit", value="all")
        
        # Advanced filters
        with st.expander("🔍 Advanced Filters"):
            days_back = st.slider("Days Back (0 = all time)", min_value=0, max_value=365, value=0)
            min_score = st.slider("Minimum Score", min_value=0, max_value=100, value=0)
            min_comments = st.slider("Minimum Comments", min_value=0, max_value=50, value=0)
            min_engagement = st.slider("Minimum Engagement Rate", min_value=0.0, max_value=20.0, value=0.0, step=0.5)
            sentiment_filter = st.selectbox("Sentiment Filter", ["all", "positive", "negative", "neutral"])
        
        # Search button
        search_button = st.button("🚀 Start Search", type="primary", use_container_width=True)
    
    # Main content
    if search_button:
        if not keywords:
            st.error("Please enter at least one keyword!")
            return
        
        # Reset results
        st.session_state.search_complete = False
        st.session_state.search_results = None
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Search configuration display
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
            # Search
            status_text.text("🔍 Searching Reddit...")
            progress_bar.progress(30)
            
            results = search_reddit(
                keywords=keywords,
                subreddit=subreddit,
                sort=sort_method,
                max_results=max_results,
                days_back=days_back if days_back > 0 else None
            )
            
            progress_bar.progress(70)
            
            if results:
                status_text.text("🔄 Applying filters...")
                
                # Apply filters
                filtered_results = []
                for post in results:
                    if post['Score'] < min_score:
                        continue
                    if post['Comments_Count'] < min_comments:
                        continue
                    if post['Engagement_Rate'] < min_engagement:
                        continue
                    if sentiment_filter != 'all' and post['Sentiment'] != sentiment_filter:
                        continue
                    
                    filtered_results.append(post)
                
                progress_bar.progress(90)
                
                if filtered_results:
                    status_text.text("📊 Preparing Excel export...")
                    
                    # Create Excel data
                    excel_data = create_excel_download(filtered_results, keywords)
                    
                    progress_bar.progress(100)
                    status_text.text("✅ Search completed successfully!")
                    
                    # Store results
                    st.session_state.search_results = filtered_results
                    st.session_state.search_complete = True
                    st.session_state.excel_data = excel_data
                    
                    st.success(f"🎉 Found {len(filtered_results)} posts (filtered from {len(results)} total)")
                else:
                    st.warning("⚠️ No posts found after applying filters. Try relaxing the criteria.")
            else:
                st.error("❌ No posts found. Try different keywords or parameters.")
                
        except Exception as e:
            st.error(f"🚨 Error during search: {str(e)}")
        finally:
            progress_bar.empty()
            status_text.empty()
    
    # Display results
    if st.session_state.search_complete and st.session_state.search_results:
        st.markdown("---")
        st.header("📊 Search Results")
        
        # Download button
        if st.session_state.excel_data:
            filename = f"reddit_search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            st.download_button(
                label="📥 Download Excel Report",
                data=st.session_state.excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel"
            )
            st.success("📁 Excel file ready for download!")
        
        # Results metrics
        results = st.session_state.search_results
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Posts Found", len(results))
        with col2:
            avg_relevance = sum(p['Relevance_Score'] for p in results) / len(results)
            st.metric("Avg Relevance", f"{avg_relevance:.1f}")
        with col3:
            positive_pct = sum(1 for p in results if p['Sentiment'] == 'positive') / len(results) * 100
            st.metric("Positive Sentiment", f"{positive_pct:.1f}%")
        
        # Visualizations
        create_visualizations(results)
        
        # Data preview
        st.subheader("📋 Data Preview")
        df = pd.DataFrame(results)
        
        # Key columns for preview
        preview_columns = ['Title', 'Subreddit', 'Score', 'Comments_Count', 'Sentiment', 'Relevance_Score', 'Date']
        available_columns = [col for col in preview_columns if col in df.columns]
        
        if available_columns:
            st.dataframe(df[available_columns].head(20), use_container_width=True)
        else:
            st.dataframe(df.head(20), use_container_width=True)
        
        # Show full data option
        if st.checkbox("📖 Show Full Dataset"):
            st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()