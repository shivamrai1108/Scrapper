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
            
            /* Discover Subreddits Modal */
            .discover-btn { 
                background: #ff6b35; color: white; border: none; cursor: pointer;
                font-size: 14px; padding: 8px 16px; border-radius: 4px; margin-top: 8px;
                font-weight: bold; transition: background 0.3s; width: auto;
            }
            .discover-btn:hover { background: #e55a2e; }
            
            .modal {
                display: none; position: fixed; z-index: 1000; left: 0; top: 0;
                width: 100%; height: 100%; background-color: rgba(0,0,0,0.5);
                animation: fadeIn 0.3s;
            }
            .modal-content {
                background-color: white; margin: 3% auto; padding: 0;
                border-radius: 12px; width: 90%; max-width: 800px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                animation: slideIn 0.3s;
            }
            .modal-header {
                padding: 20px 30px; border-bottom: 1px solid #eee;
                display: flex; justify-content: space-between; align-items: center;
                background: #f8f9fa; border-radius: 12px 12px 0 0;
            }
            .modal-title { font-size: 1.4rem; font-weight: bold; color: #333; }
            .close-btn {
                background: none; border: none; font-size: 28px;
                cursor: pointer; color: #999; width: auto;
            }
            .close-btn:hover { color: #333; }
            .modal-body { padding: 30px; max-height: 500px; overflow-y: auto; }
            .modal-footer {
                padding: 20px 30px; border-top: 1px solid #eee;
                text-align: right; background: #f8f9fa;
                border-radius: 0 0 12px 12px;
            }
            
            .modal-search {
                margin-bottom: 25px; padding: 20px;
                background: #f0f9ff; border-radius: 8px;
            }
            .modal-search input {
                width: 100%; padding: 12px; border: 2px solid #ddd;
                border-radius: 6px; font-size: 16px; margin-bottom: 10px;
            }
            .modal-search input:focus { outline: none; border-color: #ff6b35; }
            .search-btn {
                background: #ff6b35; color: white; border: none;
                padding: 10px 20px; border-radius: 6px; cursor: pointer;
                font-weight: bold; width: auto;
            }
            .search-btn:hover { background: #e55a2e; }
            
            .selected-subreddits {
                margin-bottom: 20px; padding: 15px;
                background: #e3f2fd; border-radius: 8px;
            }
            .selected-title { font-weight: bold; margin-bottom: 10px; color: #1565c0; }
            .selected-item {
                display: inline-flex; align-items: center; background: white;
                padding: 6px 12px; margin: 4px; border-radius: 20px;
                border: 1px solid #1565c0; font-size: 13px;
            }
            .selected-name { color: #1565c0; font-weight: bold; }
            .remove-btn {
                background: #f44336; color: white; border: none;
                width: 18px; height: 18px; border-radius: 50%;
                margin-left: 8px; cursor: pointer; font-size: 10px;
            }
            .remove-btn:hover { background: #d32f2f; }
            
            .subreddit-results {
                background: white; border-radius: 8px; border: 1px solid #ddd;
            }
            .subreddit-item {
                display: flex; align-items: center; justify-content: space-between;
                padding: 12px; border-bottom: 1px solid #eee;
            }
            .subreddit-item:last-child { border-bottom: none; }
            .subreddit-info { flex-grow: 1; }
            .subreddit-name { font-weight: bold; color: #1a73e8; }
            .subreddit-stats { color: #666; font-size: 12px; margin-top: 4px; }
            .subreddit-description { color: #888; font-size: 11px; margin-top: 2px; }
            .add-btn {
                background: #28a745; color: white; border: none;
                padding: 8px 16px; border-radius: 6px; cursor: pointer;
                font-size: 12px; font-weight: bold; width: auto;
            }
            .add-btn:hover { background: #218838; }
            .add-btn:disabled { background: #6c757d; cursor: not-allowed; }
            
            .modal-loading {
                text-align: center; padding: 20px;
            }
            .modal-spinner {
                border: 3px solid #f3f3f3; border-top: 3px solid #ff6b35;
                border-radius: 50%; width: 30px; height: 30px;
                animation: spin 1s linear infinite; margin: 0 auto 15px;
            }
            
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            @keyframes slideIn { from { transform: translateY(-50px); } to { transform: translateY(0); } }
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
                            <textarea id="keywords" name="keywords" placeholder="Gong
fathom
HubSpot
Salesforce" required></textarea>
                        </div>
                        <div class="form-group half">
                            <label for="subreddit">Subreddit</label>
                            <input type="text" id="subreddit" name="subreddit" value="all" placeholder="all, saas, startups, entrepreneur">
                            <small style="color: #666; font-size: 12px; margin-top: 5px; display: block;">Enter 'all' for all Reddit or specific subreddit name (e.g., 'saas', 'startups')</small>
                            <button type="button" class="discover-btn" onclick="openDiscoverModal()">🔍 Discover Subreddits</button>
                        </div>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label for="max_results">Max Results</label>
                            <select id="max_results" name="max_results">
                                <option value="25">25</option>
                                <option value="50">50</option>
                                <option value="100" selected>100</option>
                                <option value="250">250</option>
                                <option value="500">500</option>
                                <option value="1000">1,000</option>
                                <option value="2500">2,500</option>
                                <option value="5000">5,000</option>
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
                <p><strong id="loadingText">Searching Reddit and analyzing data...</strong></p>
                <p id="loadingSubtext">This may take a few moments depending on the number of results.</p>
                <div id="progressInfo" style="margin-top: 15px; padding: 10px; background: #f0f9ff; border-radius: 5px; display: none;">
                    <p style="margin: 0; font-size: 14px; color: #666;">⚡ Pro tip: Larger searches (1000+ posts) may take 1-2 minutes for comprehensive analysis</p>
                </div>
            </div>
            
            <div id="results" class="results" style="display: none;">
                <div class="results-card">
                    <div id="metrics" class="metrics">
                        <!-- Metrics will be populated here -->
                    </div>
                    <div id="downloadSection" style="display: none; text-align: center; margin: 20px 0; padding: 20px; background: #f0f9ff; border-radius: 10px; border: 2px dashed #1a73e8;">
                        <h4 style="color: #1a73e8; margin-bottom: 10px;">📊 Export Your Data</h4>
                        <button id="downloadBtn" class="download-btn" style="font-size: 18px; padding: 15px 40px;">📥 Download Excel Report</button>
                        <p style="color: #666; margin-top: 10px; font-size: 14px;">Includes all post data + analytics summary</p>
                    </div>
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
        
        <!-- Discover Subreddits Modal -->
        <div id="discoverModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 class="modal-title">🔍 Discover Subreddits</h2>
                    <button class="close-btn" onclick="closeDiscoverModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="modal-search">
                        <h4 style="margin-bottom: 10px; color: #333;">Search for Subreddits</h4>
                        <input type="text" id="modalSearchInput" placeholder="Search by topic (e.g., 'technology', 'startups', 'marketing')" onkeypress="if(event.key==='Enter') searchSubredditsInModal()">
                        <button class="search-btn" onclick="searchSubredditsInModal()">🔍 Search</button>
                    </div>
                    
                    <div id="selectedSubreddits" class="selected-subreddits" style="display: none;">
                        <div class="selected-title">🎯 Selected Subreddits:</div>
                        <div id="selectedList"></div>
                    </div>
                    
                    <div id="modalLoading" class="modal-loading" style="display: none;">
                        <div class="modal-spinner"></div>
                        <p>Searching for subreddits...</p>
                    </div>
                    
                    <div id="modalResults" style="display: none;">
                        <h4 style="margin-bottom: 15px;">Found Subreddits:</h4>
                        <div id="modalResultsList" class="subreddit-results"></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-primary" onclick="applySelectedSubreddits()" style="width: auto;">Apply Selected</button>
                    <button class="btn-primary" onclick="closeDiscoverModal()" style="background: #6c757d; margin-left: 10px; width: auto;">Cancel</button>
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
                
                // Show appropriate loading message based on search size
                const maxResults = parseInt(document.getElementById('max_results').value);
                const subredditValue = document.getElementById('subreddit').value.trim() || 'all';
                const loadingText = document.getElementById('loadingText');
                const loadingSubtext = document.getElementById('loadingSubtext');
                const progressInfo = document.getElementById('progressInfo');
                
                const subredditDisplay = subredditValue.toLowerCase() === 'all' ? 'all of Reddit' : `r/${subredditValue}`;
                
                if (maxResults >= 1000) {
                    loadingText.textContent = 'Processing large search request...';
                    loadingSubtext.textContent = `Searching ${subredditDisplay} for ${maxResults.toLocaleString()} posts with comprehensive analysis.`;
                    progressInfo.style.display = 'block';
                } else if (maxResults >= 250) {
                    loadingText.textContent = 'Searching Reddit and analyzing data...';
                    loadingSubtext.textContent = `Processing ${maxResults} posts from ${subredditDisplay} with sentiment and engagement analysis.`;
                    progressInfo.style.display = 'none';
                } else {
                    loadingText.textContent = `Searching ${subredditDisplay}...`;
                    loadingSubtext.textContent = 'Quick search in progress.';
                    progressInfo.style.display = 'none';
                }
                
                loading.style.display = 'block';
                results.style.display = 'none';
                
                const formData = new FormData(this);
                const params = new URLSearchParams(formData);
                
                try {
                    // Basic client-side validation
                    const keywords = document.getElementById('keywords').value.trim();
                    if (!keywords) {
                        loading.style.display = 'none';
                        showAlert('error', 'Please enter at least one keyword.');
                        return;
                    }

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
                const downloadSection = document.getElementById('downloadSection');
                if (downloadSection) {
                    downloadSection.style.display = 'block';
                }
                const subredditText = data.subreddit_searched ? ` in ${data.subreddit_searched}` : '';
                showAlert('success', `🎉 Found ${data.total_posts} posts${subredditText}! Analysis complete. Click download to get Excel file.`);
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
            
            // Discover Subreddits Modal Functions
            let selectedSubreddits = new Set();
            
            function openDiscoverModal() {
                document.getElementById('discoverModal').style.display = 'block';
                document.getElementById('modalSearchInput').focus();
                loadExistingSubreddits();
            }
            
            function closeDiscoverModal() {
                document.getElementById('discoverModal').style.display = 'none';
                document.getElementById('modalResults').style.display = 'none';
                document.getElementById('modalLoading').style.display = 'none';
                document.getElementById('modalSearchInput').value = '';
            }
            
            function loadExistingSubreddits() {
                const currentValue = document.getElementById('subreddit').value.trim();
                selectedSubreddits.clear();
                
                if (currentValue && currentValue.toLowerCase() !== 'all') {
                    const subreddits = currentValue.split(',').map(s => s.trim()).filter(s => s);
                    subreddits.forEach(sub => selectedSubreddits.add(sub));
                }
                
                updateSelectedDisplay();
            }
            
            async function searchSubredditsInModal() {
                const searchTerm = document.getElementById('modalSearchInput').value.trim();
                if (!searchTerm) {
                    showAlert('error', 'Please enter a search term to find subreddits.');
                    return;
                }
                
                const loading = document.getElementById('modalLoading');
                const results = document.getElementById('modalResults');
                const resultsList = document.getElementById('modalResultsList');
                
                loading.style.display = 'block';
                results.style.display = 'none';
                
                try {
                    const response = await fetch(`/api/discover_subreddits?search=${encodeURIComponent(searchTerm)}`);
                    const data = await response.json();
                    
                    loading.style.display = 'none';
                    
                    if (data.success && data.subreddits.length > 0) {
                        resultsList.innerHTML = data.subreddits.map(sub => {
                            const isSelected = selectedSubreddits.has(sub.name);
                            return `
                                <div class="subreddit-item">
                                    <div class="subreddit-info">
                                        <div class="subreddit-name">r/${sub.name}</div>
                                        <div class="subreddit-stats">${sub.subscribers.toLocaleString()} members</div>
                                        <div class="subreddit-description">${sub.description || sub.title}</div>
                                    </div>
                                    <button class="add-btn" 
                                            onclick="toggleSubreddit('${sub.name}')" 
                                            ${isSelected ? 'disabled' : ''}>
                                        ${isSelected ? '✓ Added' : '+ Add'}
                                    </button>
                                </div>
                            `;
                        }).join('');
                        results.style.display = 'block';
                    } else {
                        resultsList.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No subreddits found. Try a different search term.</p>';
                        results.style.display = 'block';
                    }
                } catch (error) {
                    loading.style.display = 'none';
                    showAlert('error', `Search failed: ${error.message}`);
                }
            }
            
            function toggleSubreddit(subredditName) {
                if (selectedSubreddits.has(subredditName)) {
                    selectedSubreddits.delete(subredditName);
                } else {
                    selectedSubreddits.add(subredditName);
                }
                
                updateSelectedDisplay();
                searchSubredditsInModal(); // Refresh results to update buttons
            }
            
            function removeSelectedSubreddit(subredditName) {
                selectedSubreddits.delete(subredditName);
                updateSelectedDisplay();
                // Update results if visible
                const searchTerm = document.getElementById('modalSearchInput').value.trim();
                if (searchTerm && document.getElementById('modalResults').style.display === 'block') {
                    searchSubredditsInModal();
                }
            }
            
            function updateSelectedDisplay() {
                const selectedSection = document.getElementById('selectedSubreddits');
                const selectedList = document.getElementById('selectedList');
                
                if (selectedSubreddits.size > 0) {
                    selectedList.innerHTML = Array.from(selectedSubreddits).map(sub => `
                        <div class="selected-item">
                            <span class="selected-name">r/${sub}</span>
                            <button class="remove-btn" onclick="removeSelectedSubreddit('${sub}')" title="Remove">×</button>
                        </div>
                    `).join('');
                    selectedSection.style.display = 'block';
                } else {
                    selectedSection.style.display = 'none';
                }
            }
            
            function applySelectedSubreddits() {
                const subredditInput = document.getElementById('subreddit');
                
                if (selectedSubreddits.size > 0) {
                    subredditInput.value = Array.from(selectedSubreddits).join(',');
                    showAlert('success', `Applied ${selectedSubreddits.size} subreddit(s) to your search!`);
                } else {
                    subredditInput.value = 'all';
                    showAlert('info', 'No subreddits selected. Set to search all of Reddit.');
                }
                
                closeDiscoverModal();
            }
            
            // Close modal when clicking outside
            window.onclick = function(event) {
                const modal = document.getElementById('discoverModal');
                if (event.target === modal) {
                    closeDiscoverModal();
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/discover_subreddits')
def discover_subreddits():
    """Discover subreddits by search term"""
    try:
        search_term = request.args.get('search', '').strip()
        if not search_term:
            return jsonify({'error': 'Search term is required', 'success': False})
        
        reddit = get_reddit_instance()
        if not reddit:
            return jsonify({'error': 'Reddit API not configured', 'success': False})
        
        discovered_subreddits = set()
        
        try:
            # Search for subreddits by name
            subreddit_results = reddit.subreddits.search_by_name(search_term, exact=False)
            for sub in subreddit_results:
                if len(discovered_subreddits) >= 25:  # Limit results
                    break
                try:
                    # Get subreddit info
                    sub_info = {
                        'name': sub.display_name,
                        'title': sub.title[:100] if hasattr(sub, 'title') and sub.title else sub.display_name,
                        'description': (sub.public_description or '')[:200] if hasattr(sub, 'public_description') else '',
                        'subscribers': getattr(sub, 'subscribers', 0) or 0,
                        'url': f'https://reddit.com/r/{sub.display_name}'
                    }
                    if sub_info['subscribers'] > 50:  # Only include active subreddits
                        discovered_subreddits.add(json.dumps(sub_info, sort_keys=True))
                except Exception:
                    continue
        except Exception:
            pass
        
        # Convert back to list and parse JSON
        subreddit_list = []
        for sub_json in list(discovered_subreddits)[:20]:  # Top 20 results
            try:
                subreddit_list.append(json.loads(sub_json))
            except Exception:
                continue
        
        # Sort by subscriber count
        subreddit_list.sort(key=lambda x: x['subscribers'], reverse=True)
        
        return jsonify({
            'success': True,
            'subreddits': subreddit_list,
            'search_term': search_term,
            'total_found': len(subreddit_list)
        })
        
    except Exception as e:
        return jsonify({'error': f'Search failed: {str(e)}', 'success': False})

@app.route('/api/advanced_search')
def api_advanced_search():
    """Advanced search API with filtering and analytics"""
    try:
        # Get parameters
        keywords_input = request.args.get('keywords', '').strip()
        subreddit = request.args.get('subreddit', 'all').strip()
        max_results = min(int(request.args.get('max_results', 50)), 5000)
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
        
        # Build search query
        search_query = ' OR '.join(keywords)
        
        # Handle subreddit selection with validation
        try:
            if subreddit.lower() == 'all':
                subreddit_obj = reddit.subreddit('all')
                subreddit_display = 'all of Reddit'
            else:
                # Handle comma-separated subreddits
                subreddit_list = [s.replace('r/', '').replace('R/', '').strip() for s in subreddit.split(',') if s.strip()]
                
                if len(subreddit_list) == 1:
                    # Single subreddit
                    clean_subreddit = subreddit_list[0]
                    subreddit_obj = reddit.subreddit(clean_subreddit)
                    
                    # Test if subreddit exists
                    try:
                        _ = subreddit_obj.display_name
                        subreddit_display = f'r/{clean_subreddit}'
                    except Exception:
                        return jsonify({
                            'success': False, 
                            'error': f'Subreddit "{clean_subreddit}" not found or is private. Please check the spelling.'
                        })
                else:
                    # Multiple subreddits - combine them
                    valid_subreddits = []
                    for sub_name in subreddit_list:
                        try:
                            test_sub = reddit.subreddit(sub_name)
                            _ = test_sub.display_name  # Test if accessible
                            valid_subreddits.append(sub_name)
                        except Exception:
                            # Skip invalid subreddits but continue
                            continue
                    
                    if not valid_subreddits:
                        return jsonify({
                            'success': False, 
                            'error': f'None of the specified subreddits were found or accessible: {subreddit_list}'
                        })
                    
                    # Create multi-subreddit object using + notation
                    subreddit_obj = reddit.subreddit('+'.join(valid_subreddits))
                    if len(valid_subreddits) == len(subreddit_list):
                        subreddit_display = f"{len(valid_subreddits)} subreddits (r/{', r/'.join(valid_subreddits)})"
                    else:
                        subreddit_display = f"{len(valid_subreddits)} valid subreddits (r/{', r/'.join(valid_subreddits)})"
                    
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'Invalid subreddit: {str(e)}'
            })
        
        posts = []
        processed_count = 0
        total_fetched = 0
        
        # Use pagination for large requests
        batch_size = min(100, max_results) if max_results > 100 else max_results
        
        try:
            for post in subreddit_obj.search(search_query, sort=sort_method, limit=max_results):
                total_fetched += 1
                
                try:
                    # Skip if post is None or deleted
                    if not post or not hasattr(post, 'title'):
                        continue
                    
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
                    
                    # Extract post data safely
                    post_data = {
                        'title': post.title[:200] if post.title else '[No Title]',
                        'subreddit': str(post.subreddit) if post.subreddit else 'unknown',
                        'author': str(post.author) if post.author else '[deleted]',
                        'score': max(0, post.score) if hasattr(post, 'score') else 0,
                        'upvote_ratio': round(post.upvote_ratio, 3) if hasattr(post, 'upvote_ratio') else 0.5,
                        'num_comments': max(0, post.num_comments) if hasattr(post, 'num_comments') else 0,
                        'created_utc': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        'date': datetime.fromtimestamp(post.created_utc).strftime('%d-%m-%Y'),
                        'url': f"https://reddit.com{post.permalink}" if hasattr(post, 'permalink') else '#',
                        'content': (post.selftext[:500] + '...') if post.selftext and len(post.selftext) > 500 else (post.selftext or ''),
                        'nsfw': bool(post.over_18) if hasattr(post, 'over_18') else False,
                        'post_id': str(post.id) if hasattr(post, 'id') else f'unknown_{processed_count}',
                        'sentiment': sentiment,
                        'sentiment_score': round(sentiment_score, 4),
                        'engagement_rate': round(engagement_rate, 2),
                        'relevance_score': relevance_score,
                        'keywords_found': ', '.join([kw for kw in keywords if kw.lower() in (post.title or '').lower() or kw.lower() in (post.selftext or '').lower()])
                    }
                    posts.append(post_data)
                    processed_count += 1
                    
                    # Add small delay for large requests to be respectful
                    if processed_count % 50 == 0 and max_results > 100:
                        import time
                        time.sleep(0.1)
                        
                except Exception as post_error:
                    # Continue processing other posts if one fails
                    continue
                    
        except Exception as search_error:
            return jsonify({
                'success': False, 
                'error': f'Search failed: {str(search_error)}'
            })
        
        # Calculate actual search time based on processing
        search_time = max(0.5, processed_count * 0.05) + (max_results / 1000)
        
        return jsonify({
            'success': True,
            'total_posts': len(posts),
            'total_fetched': total_fetched,
            'processed_count': processed_count,
            'search_query': search_query,
            'subreddit_searched': subreddit_display,
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
            
            # Summary sheet with enhanced metrics
            summary_data = {
                'Metric': [
                    'Search Query', 'Total Posts Found', 'Unique Subreddits', 'Export Date',
                    'Average Score', 'Average Comments', 'Total Comments',
                    'Positive Sentiment %', 'Negative Sentiment %', 'Neutral Sentiment %',
                    'Average Relevance Score', 'Average Engagement Rate',
                    'Highest Score Post', 'Most Commented Post', 'Most Engaging Post'
                ],
                'Value': [
                    query,
                    len(posts),
                    df['subreddit'].nunique(),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    round(df['score'].mean(), 2),
                    round(df['num_comments'].mean(), 2),
                    df['num_comments'].sum(),
                    round((df['sentiment'] == 'positive').mean() * 100, 1),
                    round((df['sentiment'] == 'negative').mean() * 100, 1),
                    round((df['sentiment'] == 'neutral').mean() * 100, 1),
                    round(df['relevance_score'].mean(), 2),
                    round(df['engagement_rate'].mean(), 2),
                    df.loc[df['score'].idxmax(), 'title'][:50] + '...' if not df.empty else 'N/A',
                    df.loc[df['num_comments'].idxmax(), 'title'][:50] + '...' if not df.empty else 'N/A',
                    df.loc[df['engagement_rate'].idxmax(), 'title'][:50] + '...' if not df.empty else 'N/A'
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            # Top subreddits sheet
            if not df.empty:
                top_subreddits = df['subreddit'].value_counts().head(20).reset_index()
                top_subreddits.columns = ['Subreddit', 'Post_Count']
                top_subreddits['Percentage'] = round((top_subreddits['Post_Count'] / len(df)) * 100, 1)
                top_subreddits.to_excel(writer, sheet_name='Top_Subreddits', index=False)
        
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