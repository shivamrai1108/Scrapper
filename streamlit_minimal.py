#!/usr/bin/env python3
"""
Minimal Streamlit Reddit Scraper for Vercel
Optimized for deployment constraints while maintaining core functionality
"""

import streamlit as st
import pandas as pd
import os
import json
import io
import praw
from datetime import datetime, timedelta
import re

# Configure Streamlit
st.set_page_config(
    page_title="Reddit Scraper Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
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

def simple_sentiment(text):
    """Simple sentiment analysis without external libraries"""
    if not text:
        return 'neutral', 0.0
    
    text = text.lower()
    positive_words = ['good', 'great', 'excellent', 'amazing', 'awesome', 'love', 'best', 'fantastic', 'wonderful', 'perfect']
    negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible', 'disgusting', 'stupid', 'ugly', 'pathetic']
    
    pos_count = sum(word in text for word in positive_words)
    neg_count = sum(word in text for word in negative_words)
    
    if pos_count > neg_count:
        return 'positive', (pos_count - neg_count) / max(len(text.split()), 1)
    elif neg_count > pos_count:
        return 'negative', -(neg_count - pos_count) / max(len(text.split()), 1)
    else:
        return 'neutral', 0.0

def calculate_metrics(post, keywords):
    """Calculate engagement and relevance metrics"""
    # Engagement rate
    engagement_rate = (post.num_comments / max(post.score, 1)) * 100 if post.score > 0 else 0
    
    # Relevance score
    title = post.title.lower()
    content = (post.selftext or '').lower()
    relevance_score = 0
    
    for keyword in keywords:
        keyword = keyword.lower()
        relevance_score += title.count(keyword) * 20
        relevance_score += content.count(keyword) * 10
        if re.search(r'\b' + re.escape(keyword) + r'\b', title):
            relevance_score += 15
    
    return min(relevance_score, 100), engagement_rate

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
        
        for post in subreddit_obj.search(search_query, sort=sort, limit=max_results):
            # Date filtering
            if days_back:
                post_date = datetime.fromtimestamp(post.created_utc)
                cutoff_date = datetime.now() - timedelta(days=days_back)
                if post_date < cutoff_date:
                    continue
            
            # Calculate metrics
            text_to_analyze = f"{post.title} {post.selftext or ''}"
            sentiment, sentiment_score = simple_sentiment(text_to_analyze)
            relevance_score, engagement_rate = calculate_metrics(post, keywords)
            
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
                'Keywords_Found': ', '.join([kw for kw in keywords if kw.lower() in post.title.lower() or kw.lower() in (post.selftext or '').lower()])
            }
            results.append(result)
    
    except Exception as e:
        st.error(f"Search error: {e}")
        return []
    
    return results

def create_excel_download(results, keywords):
    """Create Excel file for download using minimal dependencies"""
    if not results:
        return None
    
    df = pd.DataFrame(results)
    
    # Create Excel in memory using openpyxl engine
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main data sheet
        df.to_excel(writer, sheet_name='Reddit_Data', index=False)
        
        # Summary sheet
        summary_data = {
            'Metric': ['Total Posts', 'Unique Subreddits', 'Avg Score', 'Avg Comments', 'Positive %', 'Negative %'],
            'Value': [
                len(results),
                df['Subreddit'].nunique(),
                round(df['Score'].mean(), 2),
                round(df['Comments_Count'].mean(), 2),
                round((df['Sentiment'] == 'positive').mean() * 100, 1),
                round((df['Sentiment'] == 'negative').mean() * 100, 1)
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
    
    output.seek(0)
    return output.getvalue()

def create_basic_charts(results):
    """Create basic visualizations using Streamlit native charts"""
    if not results:
        return
    
    df = pd.DataFrame(results)
    
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "😊 Sentiment", "🚀 Engagement"])
    
    with tab1:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Posts", len(results))
        with col2:
            st.metric("Avg Score", f"{df['Score'].mean():.1f}")
        with col3:
            st.metric("Total Comments", f"{df['Comments_Count'].sum():,}")
        with col4:
            st.metric("Subreddits", df['Subreddit'].nunique())
        
        # Score distribution
        st.subheader("Score Distribution")
        st.bar_chart(df['Score'].value_counts().sort_index())
        
        # Top subreddits
        st.subheader("Top Subreddits")
        top_subs = df['Subreddit'].value_counts().head(10)
        st.bar_chart(top_subs)
    
    with tab2:
        # Sentiment distribution
        sentiment_counts = df['Sentiment'].value_counts()
        st.subheader("Sentiment Distribution")
        
        # Create simple bar chart for sentiment
        col1, col2, col3 = st.columns(3)
        with col1:
            pos_count = sentiment_counts.get('positive', 0)
            st.metric("Positive", pos_count, f"{pos_count/len(df)*100:.1f}%")
        with col2:
            neu_count = sentiment_counts.get('neutral', 0)
            st.metric("Neutral", neu_count, f"{neu_count/len(df)*100:.1f}%")
        with col3:
            neg_count = sentiment_counts.get('negative', 0)
            st.metric("Negative", neg_count, f"{neg_count/len(df)*100:.1f}%")
        
        st.bar_chart(sentiment_counts)
    
    with tab3:
        # Engagement analysis
        st.subheader("Engagement vs Score")
        chart_data = df[['Score', 'Engagement_Rate']].copy()
        st.scatter_chart(chart_data.set_index('Score'))
        
        # Top engaging posts
        st.subheader("🔥 Most Engaging Posts")
        top_engaging = df.nlargest(10, 'Engagement_Rate')[['Title', 'Engagement_Rate', 'Score', 'Comments_Count']]
        st.dataframe(top_engaging, use_container_width=True)

def main():
    """Main application"""
    # Header
    st.title("🔍 Reddit Scraper Pro")
    st.markdown("**Advanced Reddit data mining with sentiment analysis and engagement metrics**")
    
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
        max_results = st.slider("Max Results", min_value=10, max_value=250, value=50, step=10)
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
        
        # Search configuration
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
        create_basic_charts(results)
        
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