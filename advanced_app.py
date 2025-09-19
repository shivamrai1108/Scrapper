#!/usr/bin/env python3
"""
Advanced Flask Reddit Scraper
Complete analytics dashboard with sentiment analysis, engagement metrics, and Excel export
"""

from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import io
import praw
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import re

app = Flask(__name__)

def get_reddit_instance():
    """Get Reddit API instance"""
    try:
        return praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID', '').strip(),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET', '').strip(),
            user_agent=os.getenv('REDDIT_USER_AGENT', 'RedditScraper/1.0').strip()
        )
    except Exception as e:
        return None

def simple_sentiment(text):
    """Simple sentiment analysis without external libraries"""
    if not text:
        return 'neutral', 0.0
    
    text = text.lower()
    positive_words = ['good', 'great', 'excellent', 'amazing', 'awesome', 'love', 'best', 'fantastic', 'wonderful', 'perfect', 'incredible', 'outstanding', 'brilliant', 'superb']
    negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible', 'disgusting', 'stupid', 'ugly', 'pathetic', 'useless', 'garbage', 'trash', 'disappointing']
    
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
        # Title matches get higher score
        relevance_score += title.count(keyword) * 20
        # Content matches
        relevance_score += content.count(keyword) * 10
        # Exact word boundary matches get bonus
        if re.search(r'\\b' + re.escape(keyword) + r'\\b', title):
            relevance_score += 15
        if re.search(r'\\b' + re.escape(keyword) + r'\\b', content):
            relevance_score += 5
    
    return min(relevance_score, 100), engagement_rate

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔍 Reddit Scraper Pro</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .header h1 { color: #1a73e8; font-size: 2.5rem; margin-bottom: 10px; }
            .header p { color: #666; font-size: 1.1rem; }
            
            .search-card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .form-row { display: flex; gap: 20px; margin-bottom: 20px; align-items: end; }
            .form-group { flex: 1; }
            .form-group.half { flex: 0.5; }
            
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
            input, select, textarea, button { 
                width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; 
                font-size: 14px; transition: border-color 0.3s;
            }
            input:focus, select:focus, textarea:focus { outline: none; border-color: #1a73e8; }
            textarea { resize: vertical; min-height: 100px; }
            
            .btn-primary { 
                background: #1a73e8; color: white; border: none; cursor: pointer; 
                font-weight: bold; font-size: 16px; padding: 15px;
            }
            .btn-primary:hover { background: #1557b0; }
            
            .filters { background: #f1f3f4; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .filters h3 { margin-bottom: 15px; color: #333; }
            
            #loading { 
                display: none; text-align: center; padding: 40px; 
                background: white; border-radius: 10px; margin: 20px 0;
            }
            .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #1a73e8; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 0 auto 20px; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            
            .results { margin-top: 30px; }
            .results-card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
            
            .metrics { display: flex; gap: 20px; margin-bottom: 30px; }
            .metric { flex: 1; text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px; }
            .metric-value { font-size: 2rem; font-weight: bold; color: #1a73e8; }
            .metric-label { color: #666; margin-top: 5px; }
            
            .tabs { display: flex; border-bottom: 2px solid #eee; margin-bottom: 20px; }
            .tab { padding: 12px 24px; cursor: pointer; background: none; border: none; font-size: 16px; }
            .tab.active { border-bottom: 2px solid #1a73e8; color: #1a73e8; font-weight: bold; }
            .tab:hover { background: #f8f9fa; }
            
            .tab-content { display: none; }
            .tab-content.active { display: block; }
            
            .data-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            .data-table th, .data-table td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
            .data-table th { background: #f8f9fa; font-weight: bold; }
            .data-table tr:hover { background: #f8f9fa; }
            .data-table a { color: #1a73e8; text-decoration: none; }
            .data-table a:hover { text-decoration: underline; }
            
            .download-btn { 
                background: #0f9d58; color: white; padding: 15px 30px; 
                border: none; border-radius: 6px; font-size: 16px; font-weight: bold; 
                cursor: pointer; margin: 20px 0; display: inline-block; text-decoration: none;
            }
            .download-btn:hover { background: #0d8043; }
            
            .alert { padding: 15px; border-radius: 6px; margin: 15px 0; }
            .alert.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .alert.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .alert.info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Reddit Scraper Pro</h1>
                <p>Advanced Reddit data mining with sentiment analysis, engagement metrics, and Excel export</p>
            </div>
            
            <div class="search-card">
                <form id="searchForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="keywords">Keywords (one per line)</label>
                            <textarea id="keywords" name="keywords" placeholder="Python
artificial intelligence
machine learning" required></textarea>
                        </div>
                        <div class="form-group half">
                            <label for="subreddit">Subreddit</label>
                            <input type="text" id="subreddit" name="subreddit" value="all" placeholder="all or specific subreddit">
                        </div>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label for="max_results">Max Results</label>
                            <select id="max_results" name="max_results">
                                <option value="25">25</option>
                                <option value="50" selected>50</option>
                                <option value="100">100</option>
                                <option value="200">200</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="sort_method">Sort Method</label>
                            <select id="sort_method" name="sort_method">
                                <option value="relevance" selected>Relevance</option>
                                <option value="hot">Hot</option>
                                <option value="new">New</option>
                                <option value="top">Top</option>
                                <option value="comments">Most Comments</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="days_back">Days Back (0 = all time)</label>
                            <select id="days_back" name="days_back">
                                <option value="0" selected>All Time</option>
                                <option value="1">Last 24 Hours</option>
                                <option value="7">Last Week</option>
                                <option value="30">Last Month</option>
                                <option value="90">Last 3 Months</option>
                                <option value="365">Last Year</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="filters">
                        <h3>🔍 Advanced Filters</h3>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="min_score">Minimum Score</label>
                                <input type="number" id="min_score" name="min_score" value="0" min="0">
                            </div>
                            <div class="form-group">
                                <label for="min_comments">Minimum Comments</label>
                                <input type="number" id="min_comments" name="min_comments" value="0" min="0">
                            </div>
                            <div class="form-group">
                                <label for="min_engagement">Min Engagement Rate</label>
                                <input type="number" id="min_engagement" name="min_engagement" value="0" min="0" step="0.1">
                            </div>
                            <div class="form-group">
                                <label for="sentiment_filter">Sentiment Filter</label>
                                <select id="sentiment_filter" name="sentiment_filter">
                                    <option value="all" selected>All Sentiments</option>
                                    <option value="positive">Positive Only</option>
                                    <option value="negative">Negative Only</option>
                                    <option value="neutral">Neutral Only</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn-primary">🚀 Start Advanced Search</button>
                </form>
            </div>
            
            <div id="loading">
                <div class="spinner"></div>
                <p><strong>Searching Reddit and analyzing data...</strong></p>
                <p>This may take a few moments depending on the number of results.</p>
            </div>
            
            <div id="results" class="results" style="display: none;">
                <div class="results-card">
                    <div id="metrics" class="metrics">
                        <!-- Metrics will be populated here -->
                    </div>
                    
                    <div id="downloadSection" style="display: none;">
                        <button id="downloadBtn" class="download-btn">📥 Download Excel Report</button>
                    </div>
                    
                    <div class="tabs">
                        <button class="tab active" onclick="showTab('overview')">📊 Overview</button>
                        <button class="tab" onclick="showTab('sentiment')">😊 Sentiment</button>
                        <button class="tab" onclick="showTab('engagement')">🚀 Engagement</button>
                        <button class="tab" onclick="showTab('data')">📋 Data Preview</button>
                    </div>
                    
                    <div id="tab-overview" class="tab-content active">
                        <h3>📊 Search Overview</h3>
                        <div id="overviewContent"></div>
                    </div>
                    
                    <div id="tab-sentiment" class="tab-content">
                        <h3>😊 Sentiment Analysis</h3>
                        <div id="sentimentContent"></div>
                    </div>
                    
                    <div id="tab-engagement" class="tab-content">
                        <h3>🚀 Engagement Analysis</h3>
                        <div id="engagementContent"></div>
                    </div>
                    
                    <div id="tab-data" class="tab-content">
                        <h3>📋 Data Preview</h3>
                        <div id="dataContent"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let searchResults = null;
            let searchQuery = '';
            
            // Tab functionality
            function showTab(tabName) {
                // Hide all tabs
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                // Show selected tab
                document.getElementById(`tab-${tabName}`).classList.add('active');
                event.target.classList.add('active');
            }
            
            // Form submission
            document.getElementById('searchForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const loading = document.getElementById('loading');
                const results = document.getElementById('results');
                
                loading.style.display = 'block';
                results.style.display = 'none';
                
                const formData = new FormData(this);
                const params = new URLSearchParams(formData);
                
                try {
                    const response = await fetch('/api/advanced_search?' + params.toString());
                    const data = await response.json();
                    
                    loading.style.display = 'none';
                    
                    if (data.success) {
                        searchResults = data.posts;
                        searchQuery = data.search_query;
                        displayResults(data);
                        results.style.display = 'block';
                    } else {
                        showAlert('error', `Error: ${data.error}`);
                    }
                } catch (error) {
                    loading.style.display = 'none';
                    showAlert('error', `Network error: ${error.message}`);
                }
            });
            
            function displayResults(data) {
                // Display metrics
                displayMetrics(data);
                
                // Display analytics
                displayOverview(data.posts);
                displaySentiment(data.posts);
                displayEngagement(data.posts);
                displayData(data.posts);
                
                // Show download section
                document.getElementById('downloadSection').style.display = 'block';
                showAlert('success', `🎉 Found ${data.total_posts} posts! Analysis complete.`);
            }
            
            function displayMetrics(data) {
                const metrics = document.getElementById('metrics');
                const posts = data.posts;
                
                const avgScore = posts.reduce((sum, p) => sum + p.score, 0) / posts.length;
                const totalComments = posts.reduce((sum, p) => sum + p.num_comments, 0);
                const avgRelevance = posts.reduce((sum, p) => sum + p.relevance_score, 0) / posts.length;
                const positivePct = posts.filter(p => p.sentiment === 'positive').length / posts.length * 100;
                
                metrics.innerHTML = `
                    <div class="metric">
                        <div class="metric-value">${data.total_posts}</div>
                        <div class="metric-label">Posts Found</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${avgScore.toFixed(1)}</div>
                        <div class="metric-label">Avg Score</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${totalComments.toLocaleString()}</div>
                        <div class="metric-label">Total Comments</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${avgRelevance.toFixed(1)}</div>
                        <div class="metric-label">Avg Relevance</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${positivePct.toFixed(1)}%</div>
                        <div class="metric-label">Positive Sentiment</div>
                    </div>
                `;
            }
            
            function displayOverview(posts) {
                const subredditCounts = {};
                posts.forEach(p => {
                    subredditCounts[p.subreddit] = (subredditCounts[p.subreddit] || 0) + 1;
                });
                
                const topSubreddits = Object.entries(subredditCounts)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 10);
                
                const overviewContent = document.getElementById('overviewContent');
                overviewContent.innerHTML = `
                    <h4>Top Subreddits</h4>
                    <table class="data-table">
                        <thead>
                            <tr><th>Subreddit</th><th>Posts</th><th>Percentage</th></tr>
                        </thead>
                        <tbody>
                            ${topSubreddits.map(([sub, count]) => `
                                <tr>
                                    <td>r/${sub}</td>
                                    <td>${count}</td>
                                    <td>${(count/posts.length*100).toFixed(1)}%</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            }
            
            function displaySentiment(posts) {
                const sentimentCounts = {
                    positive: posts.filter(p => p.sentiment === 'positive').length,
                    neutral: posts.filter(p => p.sentiment === 'neutral').length,
                    negative: posts.filter(p => p.sentiment === 'negative').length
                };
                
                const sentimentContent = document.getElementById('sentimentContent');
                sentimentContent.innerHTML = `
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-value" style="color: #0f9d58;">${sentimentCounts.positive}</div>
                            <div class="metric-label">Positive (${(sentimentCounts.positive/posts.length*100).toFixed(1)}%)</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" style="color: #9aa0a6;">${sentimentCounts.neutral}</div>
                            <div class="metric-label">Neutral (${(sentimentCounts.neutral/posts.length*100).toFixed(1)}%)</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" style="color: #ea4335;">${sentimentCounts.negative}</div>
                            <div class="metric-label">Negative (${(sentimentCounts.negative/posts.length*100).toFixed(1)}%)</div>
                        </div>
                    </div>
                    
                    <h4>Sample Positive Posts</h4>
                    <table class="data-table">
                        <thead>
                            <tr><th>Title</th><th>Score</th><th>Subreddit</th></tr>
                        </thead>
                        <tbody>
                            ${posts.filter(p => p.sentiment === 'positive').slice(0, 5).map(p => `
                                <tr>
                                    <td><a href="${p.url}" target="_blank">${p.title.substring(0, 80)}...</a></td>
                                    <td>${p.score}</td>
                                    <td>r/${p.subreddit}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            }
            
            function displayEngagement(posts) {
                const topEngaging = posts
                    .sort((a, b) => b.engagement_rate - a.engagement_rate)
                    .slice(0, 10);
                
                const engagementContent = document.getElementById('engagementContent');
                engagementContent.innerHTML = `
                    <h4>🔥 Most Engaging Posts</h4>
                    <table class="data-table">
                        <thead>
                            <tr><th>Title</th><th>Engagement Rate</th><th>Score</th><th>Comments</th><th>Subreddit</th></tr>
                        </thead>
                        <tbody>
                            ${topEngaging.map(p => `
                                <tr>
                                    <td><a href="${p.url}" target="_blank">${p.title.substring(0, 60)}...</a></td>
                                    <td>${p.engagement_rate.toFixed(2)}%</td>
                                    <td>${p.score}</td>
                                    <td>${p.num_comments}</td>
                                    <td>r/${p.subreddit}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            }
            
            function displayData(posts) {
                const dataContent = document.getElementById('dataContent');
                dataContent.innerHTML = `
                    <p><strong>Showing first 20 posts</strong> (download Excel for complete data)</p>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Title</th>
                                <th>Subreddit</th>
                                <th>Score</th>
                                <th>Comments</th>
                                <th>Sentiment</th>
                                <th>Relevance</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${posts.slice(0, 20).map(p => `
                                <tr>
                                    <td><a href="${p.url}" target="_blank">${p.title.substring(0, 50)}...</a></td>
                                    <td>r/${p.subreddit}</td>
                                    <td>${p.score}</td>
                                    <td>${p.num_comments}</td>
                                    <td style="color: ${p.sentiment === 'positive' ? '#0f9d58' : p.sentiment === 'negative' ? '#ea4335' : '#9aa0a6'}">${p.sentiment}</td>
                                    <td>${p.relevance_score}</td>
                                    <td>${p.date}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            }
            
            // Download functionality
            document.getElementById('downloadBtn').addEventListener('click', function() {
                if (searchResults) {
                    downloadExcel(searchResults, searchQuery);
                }
            });
            
            function downloadExcel(posts, query) {
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '/download_excel';
                
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'data';
                input.value = JSON.stringify({posts, query});
                
                form.appendChild(input);
                document.body.appendChild(form);
                form.submit();
                document.body.removeChild(form);
            }
            
            function showAlert(type, message) {
                const alert = document.createElement('div');
                alert.className = `alert ${type}`;
                alert.innerHTML = message;
                
                document.querySelector('.container').insertBefore(alert, document.querySelector('.search-card'));
                
                setTimeout(() => alert.remove(), 5000);
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/advanced_search')
def api_advanced_search():
    """Advanced search API with filtering and analytics"""
    try:
        # Get parameters
        keywords_input = request.args.get('keywords', '').strip()
        subreddit = request.args.get('subreddit', 'all').strip()
        max_results = min(int(request.args.get('max_results', 50)), 200)
        sort_method = request.args.get('sort_method', 'relevance')
        days_back = int(request.args.get('days_back', 0))
        min_score = int(request.args.get('min_score', 0))
        min_comments = int(request.args.get('min_comments', 0))
        min_engagement = float(request.args.get('min_engagement', 0.0))
        sentiment_filter = request.args.get('sentiment_filter', 'all')
        
        # Parse keywords
        keywords = [k.strip() for k in keywords_input.split('\n') if k.strip()]
        
        if not keywords:
            return jsonify({'success': False, 'error': 'Keywords are required'})
        
        # Get Reddit instance
        reddit = get_reddit_instance()
        if not reddit:
            return jsonify({'success': False, 'error': 'Reddit API connection failed'})
        
        # Search posts
        search_query = ' OR '.join(keywords)
        
        if subreddit.lower() == 'all':
            subreddit_obj = reddit.subreddit('all')
        else:
            subreddit_obj = reddit.subreddit(subreddit)
        
        posts = []
        
        for post in subreddit_obj.search(search_query, sort=sort_method, limit=max_results):
            # Date filtering
            if days_back > 0:
                post_date = datetime.fromtimestamp(post.created_utc)
                cutoff_date = datetime.now() - timedelta(days=days_back)
                if post_date < cutoff_date:
                    continue
            
            # Calculate metrics
            text_to_analyze = f"{post.title} {post.selftext or ''}"
            sentiment, sentiment_score = simple_sentiment(text_to_analyze)
            relevance_score, engagement_rate = calculate_metrics(post, keywords)
            
            # Apply filters
            if post.score < min_score:
                continue
            if post.num_comments < min_comments:
                continue
            if engagement_rate < min_engagement:
                continue
            if sentiment_filter != 'all' and sentiment != sentiment_filter:
                continue
            
            post_data = {
                'title': post.title,
                'subreddit': str(post.subreddit),
                'author': str(post.author) if post.author else '[deleted]',
                'score': post.score,
                'upvote_ratio': post.upvote_ratio,
                'num_comments': post.num_comments,
                'created_utc': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                'date': datetime.fromtimestamp(post.created_utc).strftime('%d-%m-%Y'),
                'url': f"https://reddit.com{post.permalink}",
                'content': post.selftext[:500] + '...' if len(post.selftext or '') > 500 else post.selftext or '',
                'nsfw': post.over_18,
                'post_id': post.id,
                'sentiment': sentiment,
                'sentiment_score': sentiment_score,
                'engagement_rate': engagement_rate,
                'relevance_score': relevance_score,
                'keywords_found': ', '.join([kw for kw in keywords if kw.lower() in post.title.lower() or kw.lower() in (post.selftext or '').lower()])
            }
            posts.append(post_data)
        
        search_time = len(posts) * 0.1  # Simulated search time
        
        return jsonify({
            'success': True,
            'total_posts': len(posts),
            'search_query': search_query,
            'search_time': f"{search_time:.2f} seconds",
            'posts': posts
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download_excel', methods=['POST'])
def download_excel():
    """Generate and download Excel file"""
    try:
        data = json.loads(request.form.get('data', '{}'))
        posts = data.get('posts', [])
        query = data.get('query', 'reddit_search')
        
        if not posts:
            return jsonify({'error': 'No data to download'})
        
        # Create DataFrame
        df = pd.DataFrame(posts)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Main data sheet
            df.to_excel(writer, sheet_name='Reddit_Data', index=False)
            
            # Summary sheet
            summary_data = {
                'Metric': [
                    'Total Posts', 'Unique Subreddits', 'Avg Score', 'Avg Comments',
                    'Positive Sentiment %', 'Negative Sentiment %', 'Neutral Sentiment %',
                    'Avg Relevance Score', 'Avg Engagement Rate'
                ],
                'Value': [
                    len(posts),
                    df['subreddit'].nunique(),
                    round(df['score'].mean(), 2),
                    round(df['num_comments'].mean(), 2),
                    round((df['sentiment'] == 'positive').mean() * 100, 1),
                    round((df['sentiment'] == 'negative').mean() * 100, 1),
                    round((df['sentiment'] == 'neutral').mean() * 100, 1),
                    round(df['relevance_score'].mean(), 2),
                    round(df['engagement_rate'].mean(), 2)
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
        
        output.seek(0)
        
        filename = f"reddit_scraper_results_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            io.BytesIO(output.getvalue()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Reddit Scraper Pro Advanced'})

if __name__ == '__main__':
    app.run(debug=True)