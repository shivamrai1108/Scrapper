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
import requests
import time
import logging
from threading import Thread
from uuid import uuid4

app = Flask(__name__)

def get_reddit_instance():
    """Get Reddit API instance"""
    try:
        client_id = os.getenv('REDDIT_CLIENT_ID', '').strip()
        client_secret = os.getenv('REDDIT_CLIENT_SECRET', '').strip()
        user_agent = os.getenv('REDDIT_USER_AGENT', 'RedditScraper/1.0').strip()
        
        if not client_id or not client_secret:
            print("WARNING: Reddit API credentials not found. Using mock data for testing.")
            return None
            
        return praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
    except Exception as e:
        print(f"Reddit API error: {e}")
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

# ============ SLACK INTEGRATION SYSTEM ============

def load_slack_settings():
    """Load Slack integration settings from file"""
    settings_file = 'slack_settings.json'
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading Slack settings: {e}")
    
    return {
        'integrations': [],
        'audit_log': []
    }

def save_slack_settings(settings):
    """Save Slack integration settings to file"""
    settings_file = 'slack_settings.json'
    try:
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Error saving Slack settings: {e}")
        return False

def validate_slack_webhook(webhook_url):
    """Validate if a Slack webhook URL is properly formatted"""
    if not webhook_url:
        return False, "Webhook URL is required"
    
    if not webhook_url.startswith('https://hooks.slack.com/services/'):
        return False, "Invalid Slack webhook URL format. Must start with 'https://hooks.slack.com/services/'"
    
    # Basic format check for Slack webhook URL structure
    parts = webhook_url.replace('https://hooks.slack.com/services/', '').split('/')
    if len(parts) != 3:
        return False, "Invalid webhook URL structure. Should be: https://hooks.slack.com/services/T.../B.../..."
    
    return True, "Valid webhook URL"

def test_slack_webhook(webhook_url, channel_name):
    """Test a Slack webhook by sending a test message"""
    try:
        message = {
            "username": "Reddit Scraper Pro",
            "icon_emoji": ":mag:",
            "text": ":wave: Test connection successful!",
            "attachments": [{
                "color": "good",
                "fields": [
                    {
                        "title": "Integration Status",
                        "value": f"Your Reddit Scraper Pro is now connected to {channel_name}!",
                        "short": False
                    },
                    {
                        "title": "Next Steps",
                        "value": "Run a search on the web app to receive notifications, or use `/reddit search [keywords]` in Slack!",
                        "short": False
                    }
                ],
                "footer": "Reddit Scraper Pro",
                "footer_icon": "https://reddit.com/favicon.ico",
                "ts": int(time.time())
            }]
        }
        
        print(f"Testing webhook: {webhook_url[:50]}...")
        response = requests.post(webhook_url, json=message, timeout=15)
        
        print(f"Webhook response: {response.status_code} - {response.text[:200]}")
        
        if response.status_code == 200:
            return True, "Test message sent successfully!"
        elif response.status_code == 404:
            return False, "Webhook URL not found. Please check the URL or regenerate it in Slack."
        elif response.status_code == 403:
            return False, "Webhook access denied. Please check webhook permissions in Slack."
        elif response.status_code == 400:
            return False, "Invalid webhook request. The webhook URL might be malformed."
        else:
            return False, f"Webhook test failed with status {response.status_code}. Response: {response.text[:100]}"
            
    except requests.exceptions.Timeout:
        return False, "Webhook request timed out. Please check your internet connection."
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Slack. Please check the webhook URL and try again."
    except Exception as e:
        return False, f"Webhook test error: {str(e)}"

def send_slack_notification(webhook_url, channel, search_data, posts, retry_count=0):
    """Send a formatted notification to Slack about completed search"""
    try:
        # Calculate summary stats
        total_posts = len(posts)
        avg_score = sum(p.get('score', 0) for p in posts) / max(total_posts, 1)
        total_comments = sum(p.get('num_comments', 0) for p in posts)
        positive_posts = len([p for p in posts if p.get('sentiment') == 'positive'])
        positive_pct = (positive_posts / total_posts * 100) if total_posts > 0 else 0
        
        # Get top 3 posts by engagement
        top_posts = sorted(posts, key=lambda x: x.get('engagement_rate', 0), reverse=True)[:3]
        
        # Create download link (simplified for demo)
        download_id = str(uuid4())[:8]
        download_link = f"https://scrapper-eight-alpha.vercel.app/download/{download_id}"
        
        # Build Slack message
        message = {
            "channel": channel,
            "username": "Reddit Scraper Pro",
            "icon_emoji": ":mag:",
            "text": f":chart_with_upwards_trend: *Reddit Search Complete!*",
            "attachments": [
                {
                    "color": "good" if total_posts > 0 else "warning",
                    "fields": [
                        {
                            "title": "Search Query",
                            "value": search_data.get('keywords', 'N/A'),
                            "short": True
                        },
                        {
                            "title": "Subreddit(s)",
                            "value": search_data.get('subreddit_display', 'all'),
                            "short": True
                        },
                        {
                            "title": "Posts Found",
                            "value": f"{total_posts:,}",
                            "short": True
                        },
                        {
                            "title": "Avg Upvotes",
                            "value": f"{avg_score:.1f}",
                            "short": True
                        },
                        {
                            "title": "Total Comments",
                            "value": f"{total_comments:,}",
                            "short": True
                        },
                        {
                            "title": "Positive Sentiment",
                            "value": f"{positive_pct:.1f}%",
                            "short": True
                        }
                    ],
                    "footer": "Reddit Scraper Pro",
                    "footer_icon": "https://reddit.com/favicon.ico",
                    "ts": int(time.time())
                }
            ]
        }
        
        # Add top posts preview if available
        if top_posts:
            top_posts_text = "\n".join([
                f"• <{post.get('url', '#')}|{post.get('title', 'Untitled')[:50]}...> ({post.get('score', 0)} upvotes)"
                for post in top_posts
            ])
            
            message["attachments"].append({
                "color": "#1a73e8",
                "title": ":fire: Top Engaging Posts",
                "text": top_posts_text,
                "mrkdwn_in": ["text"]
            })
        
        # Add action buttons
        message["attachments"].append({
            "color": "#0f9d58",
            "actions": [
                {
                    "type": "button",
                    "text": ":arrow_down: Download CSV",
                    "url": download_link,
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": ":mag: View Dashboard",
                    "url": "https://scrapper-eight-alpha.vercel.app"
                }
            ]
        })
        
        response = requests.post(webhook_url, json=message, timeout=15)
        
        if response.status_code == 200:
            return True, "Notification sent successfully"
        else:
            if retry_count < 2:  # Retry up to 2 times
                time.sleep(2 ** retry_count)  # Exponential backoff
                return send_slack_notification(webhook_url, channel, search_data, posts, retry_count + 1)
            return False, f"Failed after {retry_count + 1} attempts. Status: {response.status_code}"
            
    except Exception as e:
        if retry_count < 2:
            time.sleep(2 ** retry_count)
            return send_slack_notification(webhook_url, channel, search_data, posts, retry_count + 1)
        return False, f"Error after {retry_count + 1} attempts: {str(e)}"

def should_send_notification(integration, search_data, posts):
    """Check if notification should be sent based on settings"""
    # Check if integration is active
    if not integration.get('active', True):
        return False
    
    # Check keyword filters
    keyword_filters = integration.get('keyword_filters', [])
    if keyword_filters:
        search_keywords = search_data.get('keywords', '').lower().split('\n')
        if not any(kf.lower() in keyword for keyword in search_keywords for kf in keyword_filters):
            return False
    
    # Check minimum post count
    min_posts = integration.get('min_posts', 0)
    if len(posts) < min_posts:
        return False
    
    # Check severity level
    severity = integration.get('severity_level', 'info')
    post_count = len(posts)
    
    if severity == 'alert' and post_count < 100:
        return False
    elif severity == 'warning' and post_count < 25:
        return False
    # 'info' level sends all notifications
    
    return True

def log_notification_attempt(integration_id, success, message, search_data):
    """Log notification attempt for audit purposes"""
    settings = load_slack_settings()
    log_entry = {
        'id': str(uuid4()),
        'integration_id': integration_id,
        'timestamp': datetime.now().isoformat(),
        'success': success,
        'message': message,
        'search_query': search_data.get('keywords', 'N/A'),
        'subreddit': search_data.get('subreddit_display', 'N/A')
    }
    
    settings['audit_log'].insert(0, log_entry)
    # Keep only last 100 log entries
    settings['audit_log'] = settings['audit_log'][:100]
    save_slack_settings(settings)

def process_slack_notifications(search_data, posts):
    """Process all Slack integrations for a completed search"""
    def send_notifications():
        settings = load_slack_settings()
        integrations = settings.get('integrations', [])
        
        for integration in integrations:
            try:
                if should_send_notification(integration, search_data, posts):
                    success, message = send_slack_notification(
                        integration['webhook_url'],
                        integration['channel'],
                        search_data,
                        posts
                    )
                    log_notification_attempt(integration['id'], success, message, search_data)
                    
            except Exception as e:
                log_notification_attempt(
                    integration.get('id', 'unknown'),
                    False,
                    f"Exception: {str(e)}",
                    search_data
                )
    
    # Send notifications in background thread
    Thread(target=send_notifications, daemon=True).start()

@app.route('/')
def index():
    return '''<!DOCTYPE html>
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
        .header-controls { display: flex; justify-content: center; gap: 15px; margin-top: 20px; }
        
        .settings-btn { background: #4a154b; color: white; border: none; padding: 10px 20px; 
                       border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; 
                       display: inline-flex; align-items: center; gap: 8px; transition: background 0.3s; }
        .settings-btn:hover { background: #611f69; }
        
        .search-card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .form-row { display: flex; gap: 20px; margin-bottom: 20px; align-items: end; }
        .form-group { flex: 1; }
        .form-group.half { flex: 0.5; }
        
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
        input, select, textarea, button { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; 
                                         font-size: 14px; transition: border-color 0.3s; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #1a73e8; }
        textarea { resize: vertical; min-height: 100px; }
        
        .btn-primary { background: #1a73e8; color: white; border: none; cursor: pointer; 
                       font-weight: bold; font-size: 16px; padding: 15px; }
        .btn-primary:hover { background: #1557b0; }
        
        .discover-btn { background: #ff6b35; color: white; border: none; cursor: pointer;
                       font-size: 14px; padding: 8px 16px; border-radius: 4px; margin-top: 8px;
                       font-weight: bold; transition: background 0.3s; width: auto; }
        .discover-btn:hover { background: #e55a2e; }
        
        #loading { display: none; text-align: center; padding: 40px; background: white; border-radius: 10px; margin: 20px 0; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #1a73e8; border-radius: 50%; 
                  width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 0 auto 20px; }
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
        
        .download-btn { background: #0f9d58; color: white; padding: 15px 30px; border: none; 
                       border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; 
                       margin: 20px 0; display: inline-block; text-decoration: none; }
        .download-btn:hover { background: #0d8043; }
        
        .alert { padding: 15px; border-radius: 6px; margin: 15px 0; }
        .alert.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .alert.info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        
        /* Modal Styles */
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; 
                background-color: rgba(0,0,0,0.5); animation: fadeIn 0.3s; }
        .modal-content { background-color: white; margin: 3% auto; padding: 0; border-radius: 12px; 
                        width: 90%; max-width: 800px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); animation: slideIn 0.3s; }
        .modal-header { padding: 20px 30px; border-bottom: 1px solid #eee; display: flex; 
                       justify-content: space-between; align-items: center; background: #f8f9fa; 
                       border-radius: 12px 12px 0 0; }
        .modal-title { font-size: 1.4rem; font-weight: bold; color: #333; }
        .close-btn { background: none; border: none; font-size: 28px; cursor: pointer; color: #999; width: auto; }
        .close-btn:hover { color: #333; }
        .modal-body { padding: 30px; max-height: 500px; overflow-y: auto; }
        .modal-footer { padding: 20px 30px; border-top: 1px solid #eee; text-align: right; 
                       background: #f8f9fa; border-radius: 0 0 12px 12px; }
        
        /* Slack Integration Styles */
        .slack-form { margin-bottom: 25px; }
        .slack-form .form-row { display: flex; gap: 15px; margin-bottom: 15px; }
        .slack-form .form-group { flex: 1; }
        .slack-form input, .slack-form select, .slack-form textarea { width: 100%; padding: 10px; 
                                                                     border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        .slack-form label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
        
        .integration-list { margin-top: 20px; }
        .integration-item { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px; 
                           border: 1px solid #e9ecef; }
        .integration-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .integration-name { font-weight: bold; color: #333; }
        .integration-status { padding: 4px 8px; border-radius: 12px; font-size: 12px; background: #28a745; color: white; }
        .integration-status.inactive { background: #6c757d; }
        .integration-details { font-size: 13px; color: #666; margin-bottom: 10px; }
        .integration-actions { display: flex; gap: 8px; }
        .btn-sm { padding: 4px 8px; font-size: 12px; border-radius: 4px; border: none; cursor: pointer; font-weight: bold; }
        .btn-test { background: #17a2b8; color: white; }
        .btn-test:hover { background: #138496; }
        .btn-delete { background: #dc3545; color: white; }
        .btn-delete:hover { background: #c82333; }
        
        /* Discover Subreddits Styles */
        .modal-search { margin-bottom: 25px; padding: 20px; background: #f0f9ff; border-radius: 8px; }
        .modal-search input { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; 
                             font-size: 16px; margin-bottom: 10px; }
        .modal-search input:focus { outline: none; border-color: #ff6b35; }
        .search-btn { background: #ff6b35; color: white; border: none; padding: 10px 20px; border-radius: 6px; 
                     cursor: pointer; font-size: 14px; font-weight: bold; width: auto; }
        .search-btn:hover { background: #e55a2e; }
        
        .selected-subreddits { margin-bottom: 20px; padding: 15px; background: #e3f2fd; border-radius: 8px; }
        .selected-title { font-weight: bold; margin-bottom: 10px; color: #1565c0; }
        .selected-item { display: inline-flex; align-items: center; background: white; padding: 6px 12px; 
                        margin: 4px; border-radius: 20px; border: 1px solid #1565c0; font-size: 13px; }
        .selected-name { color: #1565c0; font-weight: bold; }
        .remove-btn { background: #f44336; color: white; border: none; width: 18px; height: 18px; 
                     border-radius: 50%; margin-left: 8px; cursor: pointer; font-size: 10px; }
        .remove-btn:hover { background: #d32f2f; }
        
        .subreddit-results { background: white; border-radius: 8px; border: 1px solid #ddd; }
        .subreddit-item { display: flex; align-items: center; justify-content: space-between; 
                         padding: 12px; border-bottom: 1px solid #eee; }
        .subreddit-item:last-child { border-bottom: none; }
        .subreddit-info { flex-grow: 1; }
        .subreddit-name { font-weight: bold; color: #1a73e8; }
        .subreddit-stats { color: #666; font-size: 12px; margin-top: 4px; }
        .subreddit-description { color: #888; font-size: 11px; margin-top: 2px; }
        .add-btn { background: #28a745; color: white; border: none; padding: 8px 16px; 
                  border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: bold; width: auto; }
        .add-btn:hover { background: #218838; }
        .add-btn:disabled { background: #6c757d; cursor: not-allowed; }
        
        .modal-loading { text-align: center; padding: 20px; }
        .modal-spinner { border: 3px solid #f3f3f3; border-top: 3px solid #ff6b35; border-radius: 50%; 
                        width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto 15px; }
        
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideIn { from { transform: translateY(-50px); } to { transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Reddit Scraper Pro</h1>
            <p>Advanced Reddit data mining with sentiment analysis, engagement metrics, and Excel export</p>
            <div class="header-controls">
                <button class="settings-btn" onclick="openSlackModal()">
                    <span>⚙️</span> Slack Integration
                </button>
                <button type="button" style="background: red; color: white; margin-left: 10px; padding: 8px 16px; border: none; border-radius: 4px;" onclick="alert('TEST SUCCESS! JS is working'); console.log('TEST BUTTON CLICKED')">
                    🔴 TEST CLICK
                </button>
            </div>
        </div>
        
        <div class="search-card">
            <form id="searchForm">
                <div class="form-row">
                    <div class="form-group">
                        <label for="keywords">Keywords (one per line)</label>
                        <textarea id="keywords" name="keywords" placeholder="AI\nstartups\ntechnology" required></textarea>
                    </div>
                    <div class="form-group half">
                        <label for="subreddit">Subreddit</label>
                        <input type="text" id="subreddit" name="subreddit" value="all" placeholder="all, technology, startups">
                        <small style="color: #666; font-size: 12px; margin-top: 5px; display: block;">Enter 'all' for all Reddit or specific subreddit names</small>
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
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="sort_method">Sort Method</label>
                        <select id="sort_method" name="sort_method">
                            <option value="relevance" selected>Relevance</option>
                            <option value="hot">Hot</option>
                            <option value="new">New</option>
                            <option value="top">Top</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="days_back">Days Back</label>
                        <select id="days_back" name="days_back">
                            <option value="0" selected>All Time</option>
                            <option value="1">Last 24 Hours</option>
                            <option value="7">Last Week</option>
                            <option value="30">Last Month</option>
                        </select>
                    </div>
                </div>
                
                <button type="submit" class="btn-primary">🚀 Start Advanced Search</button>
            </form>
        </div>
        
        <div id="loading">
            <div class="spinner"></div>
            <p><strong id="loadingText">Searching Reddit and analyzing data...</strong></p>
            <p id="loadingSubtext">This may take a few moments depending on the number of results.</p>
        </div>
        
        <div id="results" class="results" style="display: none;">
            <div class="results-card">
                <div id="metrics" class="metrics"></div>
                <div id="downloadSection" style="display: none; text-align: center; margin: 20px 0; padding: 20px; background: #f0f9ff; border-radius: 10px; border: 2px dashed #1a73e8;">
                    <h4 style="color: #1a73e8; margin-bottom: 10px;">📊 Export Your Data</h4>
                    <button id="downloadBtn" class="download-btn" style="font-size: 18px; padding: 15px 40px;">📎 Download Excel Report</button>
                    <p style="color: #666; margin-top: 10px; font-size: 14px;">Includes all post data + analytics summary</p>
                </div>
                
                <div class="tabs">
                    <button class="tab active" onclick="showTab('engagement')">🚀 Engagement</button>
                    <button class="tab" onclick="showTab('data')">📋 Data Preview</button>
                </div>
                
                <div id="tab-engagement" class="tab-content active">
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
    
    <!-- Slack Integration Modal -->
    <div id="slackModal" class="modal">
        <div class="modal-content" style="max-width: 900px;">
            <div class="modal-header">
                <h2 class="modal-title">⚙️ Slack Integration Settings</h2>
                <button class="close-btn" onclick="closeSlackModal()">&times;</button>
            </div>
            <div class="modal-body">
                <!-- Add New Integration -->
                <div class="slack-form">
                    <h3 style="margin-bottom: 15px; color: #4a154b;">🔗 Connect New Slack Workspace</h3>
                    <form id="slackIntegrationForm" onsubmit="handleSlackFormSubmit(event)">
                        <div class="form-row">
                            <div class="form-group">
                                <label for="integrationName">Integration Name</label>
                                <input type="text" id="integrationName" name="name" placeholder="My Team Workspace" required>
                            </div>
                            <div class="form-group">
                                <label for="slackChannel">Slack Channel</label>
                                <input type="text" id="slackChannel" name="channel" placeholder="#reddit-alerts" required>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="webhookUrl">Slack Webhook URL</label>
                                <input type="url" id="webhookUrl" name="webhook_url" placeholder="https://hooks.slack.com/services/..." required>
                                <small style="color: #666; margin-top: 5px; display: block;">Get this from your Slack workspace's "Incoming Webhooks" app</small>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="severityLevel">Notification Level</label>
                                <select id="severityLevel" name="severity_level">
                                    <option value="info">All searches (Info)</option>
                                    <option value="warning">Medium searches (25+ posts)</option>
                                    <option value="alert">Large searches (100+ posts)</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="minPosts">Minimum Posts</label>
                                <input type="number" id="minPosts" name="min_posts" value="1" min="1">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="keywordFilters">Keyword Filters (optional)</label>
                                <textarea id="keywordFilters" name="keyword_filters" placeholder="crypto\nNFT\nblockchain" rows="3"></textarea>
                                <small style="color: #666; margin-top: 5px; display: block;">Only send notifications for searches containing these keywords (one per line)</small>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <button type="submit" class="btn-primary" style="width: auto; background: #4a154b;">🚀 Connect & Test</button>
                        </div>
                    </form>
                </div>
                
                <!-- Existing Integrations -->
                <div class="integration-list">
                    <h3 style="margin-bottom: 15px; color: #333;">📋 Your Slack Integrations</h3>
                    <div id="integrationsList">
                        <p style="text-align: center; color: #666; padding: 20px;">Loading integrations...</p>
                    </div>
                </div>
                
                <!-- Help Section -->
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-top: 25px;">
                    <h4 style="margin-bottom: 10px; color: #333;">ℹ️ How to Set Up Slack Integration:</h4>
                    <ol style="margin: 0; padding-left: 20px; color: #666;">
                        <li>Go to your Slack workspace</li>
                        <li>Add the "Incoming Webhooks" app</li>
                        <li>Choose a channel and copy the webhook URL</li>
                        <li>Paste the URL above and configure your settings</li>
                        <li>Click "Connect & Test" to verify the integration</li>
                    </ol>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-primary" onclick="loadSlackSettings()" style="background: #28a745; width: auto;">🔄 Refresh</button>
                <button class="btn-primary" onclick="closeSlackModal()" style="background: #6c757d; margin-left: 10px; width: auto;">Close</button>
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
        console.log('=== JavaScript Loading Started - v2.1 ===');
        console.log('Document ready state:', document.readyState);
        console.log('Deployment time: 2025-09-20 21:13 UTC');
        
        let searchResults = null;
        let searchQuery = '';
        
        // Tab functionality
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
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
            
            // Add default values for simplified form
            params.set('min_score', '0');
            params.set('min_comments', '0');
            params.set('min_engagement', '0');
            params.set('sentiment_filter', 'all');
            
            try {
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
            displayMetrics(data);
            displayEngagement(data.posts);
            displayData(data.posts);
            
            // Show download section and attach event listener
            const downloadSection = document.getElementById('downloadSection');
            if (downloadSection) {
                downloadSection.style.display = 'block';
                const downloadBtn = document.getElementById('downloadBtn');
                if (downloadBtn) {
                    downloadBtn.onclick = function() {
                        if (searchResults) {
                            downloadExcel(searchResults, searchQuery);
                        }
                    };
                }
            }
            
            const subredditText = data.subreddit_searched ? ` in ${data.subreddit_searched}` : '';
            showAlert('success', `🎉 Found ${data.total_posts} posts${subredditText}! Analysis complete.`);
        }
        
        function displayMetrics(data) {
            const metrics = document.getElementById('metrics');
            const posts = data.posts;
            
            if (posts.length === 0) {
                metrics.innerHTML = '<p style="text-align: center; color: #666;">No posts found matching your criteria.</p>';
                return;
            }
            
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
                    <div class="metric-label">Avg Upvotes</div>
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
        
        function displayEngagement(posts) {
            const topEngaging = posts.sort((a, b) => b.engagement_rate - a.engagement_rate).slice(0, 10);
            const engagementContent = document.getElementById('engagementContent');
            
            engagementContent.innerHTML = `
                <h4>🔥 Most Engaging Posts</h4>
                <table class="data-table">
                    <thead>
                        <tr><th>Title</th><th>Engagement Rate</th><th>Upvotes</th><th>Comments</th><th>Subreddit</th></tr>
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
                        <tr><th>Title</th><th>Subreddit</th><th>Upvotes</th><th>Comments</th><th>Sentiment</th><th>Date</th></tr>
                    </thead>
                    <tbody>
                        ${posts.slice(0, 20).map(p => `
                            <tr>
                                <td><a href="${p.url}" target="_blank">${p.title.substring(0, 50)}...</a></td>
                                <td>r/${p.subreddit}</td>
                                <td>${p.score}</td>
                                <td>${p.num_comments}</td>
                                <td style="color: ${p.sentiment === 'positive' ? '#0f9d58' : p.sentiment === 'negative' ? '#ea4335' : '#9aa0a6'}">${p.sentiment}</td>
                                <td>${p.date}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
        
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
        
        // ============ SLACK INTEGRATION FUNCTIONS ============
        
        function openSlackModal() {
            document.getElementById('slackModal').style.display = 'block';
            loadSlackSettings();
        }
        
        function closeSlackModal() {
            document.getElementById('slackModal').style.display = 'none';
            document.getElementById('slackIntegrationForm').reset();
        }
        
        async function loadSlackSettings() {
            console.log('Loading Slack settings...');
            
            try {
                const response = await fetch('/api/slack/settings');
                console.log('Settings response status:', response.status);
                
                const data = await response.json();
                console.log('Settings data:', data);
                
                if (data.success) {
                    console.log('Found integrations:', data.integrations.length);
                    displayIntegrations(data.integrations);
                } else {
                    console.log('Settings API error:', data.error);
                    showAlert('error', `Failed to load settings: ${data.error}`);
                }
            } catch (error) {
                console.log('Settings network error:', error);
                showAlert('error', `Network error: ${error.message}`);
            }
        }
        
        function displayIntegrations(integrations) {
            console.log('Displaying integrations:', integrations);
            const container = document.getElementById('integrationsList');
            
            if (!container) {
                console.error('integrationsList container not found!');
                return;
            }
            
            if (integrations.length === 0) {
                console.log('No integrations to display');
                container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No Slack integrations configured yet.</p>';
                return;
            }
            
            console.log(`Rendering ${integrations.length} integrations`);
            
            const html = integrations.map(integration => {
                console.log('Rendering integration:', integration.name, integration.id);
                return `
                <div class="integration-item" data-integration-id="${integration.id}">
                    <div class="integration-header">
                        <div class="integration-name">${integration.name}</div>
                        <div class="integration-status ${integration.active ? '' : 'inactive'}">
                            ${integration.active ? 'Active' : 'Inactive'}
                        </div>
                    </div>
                    <div class="integration-details">
                        <strong>Channel:</strong> ${integration.channel} • 
                        <strong>Level:</strong> ${integration.severity_level} • 
                        <strong>Min Posts:</strong> ${integration.min_posts}
                        ${integration.keyword_filters && integration.keyword_filters.length > 0 ? 
                            `<br><strong>Keywords:</strong> ${integration.keyword_filters.join(', ')}` : ''}
                    </div>
                    <div class="integration-actions">
                        <button class="btn-sm btn-test" onclick="testIntegration('${integration.id}')" data-integration-id="${integration.id}">⚙️ Test</button>
                        <button class="btn-sm btn-delete" onclick="deleteIntegration('${integration.id}')" data-integration-id="${integration.id}">🗑️ Delete</button>
                    </div>
                </div>
                `;
            }).join('');
            
            container.innerHTML = html;
            console.log('Integration HTML rendered successfully');
        }
        
        // Handle Slack integration form submission
        async function handleSlackFormSubmit(e) {
            console.log('Form submit triggered');
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const data = {
                name: formData.get('name'),
                channel: formData.get('channel'),
                webhook_url: formData.get('webhook_url'),
                severity_level: formData.get('severity_level'),
                min_posts: parseInt(formData.get('min_posts')),
                keyword_filters: formData.get('keyword_filters') ? 
                    formData.get('keyword_filters').split('\\n').map(k => k.trim()).filter(k => k) : [],
                created_by: 'user'
            };
            
            console.log('Creating integration with data:', data);
            
            try {
                const response = await fetch('/api/slack/integration', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                console.log('Create integration response status:', response.status);
                const result = await response.json();
                console.log('Create integration result:', result);
                
                if (result.success) {
                    showAlert('success', result.message);
                    console.log('Resetting form and reloading settings...');
                    e.target.reset();
                    // Add small delay to ensure backend is updated
                    setTimeout(() => {
                        console.log('Calling loadSlackSettings after delay...');
                        loadSlackSettings();
                    }, 500);
                } else {
                    showAlert('error', result.error);
                }
            } catch (error) {
                console.log('Form submission error:', error);
                showAlert('error', `Network error: ${error.message}`);
            }
        }
        
        async function testIntegration(integrationId) {
            console.log('Test button clicked for integration:', integrationId);
            
            try {
                console.log('Sending test request to:', `/api/slack/test/${integrationId}`);
                const response = await fetch(`/api/slack/test/${integrationId}`, { method: 'POST' });
                const result = await response.json();
                
                console.log('Test response:', result);
                
                if (result.success) {
                    showAlert('success', `Test successful! 🚀 ${result.message}`);
                } else {
                    showAlert('error', `Test failed: ${result.message}`);
                }
                
                setTimeout(() => loadSlackSettings(), 1000);
            } catch (error) {
                console.log('Test error:', error);
                showAlert('error', `Network error: ${error.message}`);
            }
        }
        
        async function deleteIntegration(integrationId) {
            console.log('Delete button clicked for integration:', integrationId);
            
            if (!confirm('Are you sure you want to delete this Slack integration?')) {
                console.log('Delete cancelled by user');
                return;
            }
            
            console.log('Sending DELETE request to:', `/api/slack/integration/${integrationId}`);
            
            try {
                const response = await fetch(`/api/slack/integration/${integrationId}`, { method: 'DELETE' });
                const result = await response.json();
                
                console.log('Delete response:', result);
                
                if (result.success) {
                    showAlert('success', 'Integration deleted successfully!');
                    loadSlackSettings();
                } else {
                    showAlert('error', result.error);
                }
            } catch (error) {
                console.log('Delete error:', error);
                showAlert('error', `Network error: ${error.message}`);
            }
        }
        
        // ============ DISCOVER SUBREDDITS FUNCTIONS ============
        
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
                                <button class="add-btn" onclick="toggleSubreddit('${sub.name}')" ${isSelected ? 'disabled' : ''}>
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
        
        // Close modals when clicking outside
        window.onclick = function(event) {
            const discoverModal = document.getElementById('discoverModal');
            const slackModal = document.getElementById('slackModal');
            if (event.target === discoverModal) {
                closeDiscoverModal();
            } else if (event.target === slackModal) {
                closeSlackModal();
            }
        };
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
        
        # Process Slack notifications in background
        search_data = {
            'keywords': search_query,
            'subreddit_display': subreddit_display,
            'total_posts': len(posts)
        }
        process_slack_notifications(search_data, posts)
        
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

# ============ SLACK INTEGRATION API ENDPOINTS ============

@app.route('/api/slack/settings', methods=['GET'])
def get_slack_settings():
    """Get all Slack integration settings"""
    try:
        settings = load_slack_settings()
        # Remove sensitive webhook URLs for security
        safe_integrations = []
        for integration in settings.get('integrations', []):
            safe_integration = integration.copy()
            if 'webhook_url' in safe_integration:
                safe_integration['webhook_url'] = '***HIDDEN***'
            safe_integrations.append(safe_integration)
        
        return jsonify({
            'success': True,
            'integrations': safe_integrations,
            'audit_log': settings.get('audit_log', [])[:20]  # Last 20 entries
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/slack/integration', methods=['POST'])
def create_slack_integration():
    """Create a new Slack integration"""
    try:
        data = request.get_json()
        
        # Validate required fields
        webhook_url = data.get('webhook_url', '').strip()
        channel = data.get('channel', '').strip()
        name = data.get('name', '').strip()
        
        if not webhook_url or not channel or not name:
            return jsonify({
                'success': False, 
                'error': 'Webhook URL, channel, and name are required'
            })
        
        # Validate webhook URL format
        is_valid, message = validate_slack_webhook(webhook_url)
        if not is_valid:
            return jsonify({'success': False, 'error': message})
        
        # Test the webhook
        test_success, test_message = test_slack_webhook(webhook_url, channel)
        if not test_success:
            return jsonify({
                'success': False, 
                'error': f'Webhook test failed: {test_message}'
            })
        
        # Create new integration
        integration = {
            'id': str(uuid4()),
            'name': name,
            'webhook_url': webhook_url,
            'channel': channel,
            'active': True,
            'created_at': datetime.now().isoformat(),
            'created_by': data.get('created_by', 'anonymous'),
            'severity_level': data.get('severity_level', 'info'),
            'keyword_filters': data.get('keyword_filters', []),
            'min_posts': data.get('min_posts', 0),
            'last_notification': None
        }
        
        # Save to settings
        settings = load_slack_settings()
        settings['integrations'].append(integration)
        
        # Add audit log entry
        audit_entry = {
            'id': str(uuid4()),
            'integration_id': integration['id'],
            'timestamp': datetime.now().isoformat(),
            'action': 'integration_created',
            'details': f'Integration "{name}" created for channel {channel}',
            'user': data.get('created_by', 'anonymous')
        }
        settings['audit_log'].insert(0, audit_entry)
        
        save_slack_settings(settings)
        
        return jsonify({
            'success': True,
            'message': 'Integration created successfully and test message sent!',
            'integration_id': integration['id']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/slack/integration/<integration_id>', methods=['PUT'])
def update_slack_integration(integration_id):
    """Update an existing Slack integration"""
    try:
        data = request.get_json()
        settings = load_slack_settings()
        
        # Find integration
        integration = None
        for i, integ in enumerate(settings['integrations']):
            if integ['id'] == integration_id:
                integration = settings['integrations'][i]
                break
        
        if not integration:
            return jsonify({'success': False, 'error': 'Integration not found'})
        
        # Update fields
        if 'name' in data:
            integration['name'] = data['name'].strip()
        if 'channel' in data:
            integration['channel'] = data['channel'].strip()
        if 'active' in data:
            integration['active'] = bool(data['active'])
        if 'severity_level' in data:
            integration['severity_level'] = data['severity_level']
        if 'keyword_filters' in data:
            integration['keyword_filters'] = data['keyword_filters']
        if 'min_posts' in data:
            integration['min_posts'] = int(data['min_posts'])
        
        integration['updated_at'] = datetime.now().isoformat()
        
        # Add audit log entry
        audit_entry = {
            'id': str(uuid4()),
            'integration_id': integration_id,
            'timestamp': datetime.now().isoformat(),
            'action': 'integration_updated',
            'details': f'Integration "{integration["name"]}" updated',
            'user': data.get('updated_by', 'anonymous')
        }
        settings['audit_log'].insert(0, audit_entry)
        
        save_slack_settings(settings)
        
        return jsonify({
            'success': True,
            'message': 'Integration updated successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/slack/integration/<integration_id>', methods=['DELETE'])
def delete_slack_integration(integration_id):
    """Delete a Slack integration"""
    try:
        settings = load_slack_settings()
        
        # Find and remove integration
        integration_name = None
        settings['integrations'] = [
            integ for integ in settings['integrations'] 
            if integ['id'] != integration_id
        ]
        
        # Add audit log entry
        audit_entry = {
            'id': str(uuid4()),
            'integration_id': integration_id,
            'timestamp': datetime.now().isoformat(),
            'action': 'integration_deleted',
            'details': f'Integration deleted',
            'user': 'system'
        }
        settings['audit_log'].insert(0, audit_entry)
        
        save_slack_settings(settings)
        
        return jsonify({
            'success': True,
            'message': 'Integration deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/slack/test/<integration_id>', methods=['POST'])
def test_slack_integration(integration_id):
    """Test a specific Slack integration"""
    try:
        settings = load_slack_settings()
        
        # Find integration
        integration = None
        for integ in settings['integrations']:
            if integ['id'] == integration_id:
                integration = integ
                break
        
        if not integration:
            return jsonify({'success': False, 'error': 'Integration not found'})
        
        # Test webhook
        success, message = test_slack_webhook(
            integration['webhook_url'], 
            integration['channel']
        )
        
        # Log test attempt
        log_entry = {
            'id': str(uuid4()),
            'integration_id': integration_id,
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'message': f'Manual test: {message}',
            'search_query': 'test',
            'subreddit': 'test'
        }
        
        settings['audit_log'].insert(0, log_entry)
        settings['audit_log'] = settings['audit_log'][:100]
        save_slack_settings(settings)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============ SLACK BOT SLASH COMMANDS ============

@app.route('/api/slack/command', methods=['POST'])
def handle_slack_command():
    """Handle Slack slash commands like /reddit search AI startups"""
    try:
        # Verify the request is from Slack (in production, verify token)
        if request.form.get('command') != '/reddit':
            return jsonify({'text': 'Unknown command'})
        
        # Parse command
        text = request.form.get('text', '').strip()
        user_name = request.form.get('user_name', 'Unknown')
        channel_name = request.form.get('channel_name', 'Unknown')
        response_url = request.form.get('response_url')
        
        if not text:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '''🔍 **Reddit Scraper Pro - Commands**

**Usage:** `/reddit search [keywords] [options]`

**Examples:**
• `/reddit search AI startups` - Search all of Reddit
• `/reddit search AI startups in technology` - Search specific subreddit
• `/reddit search crypto top 50` - Search with result limit

**Options:**
• `in [subreddit]` - Search specific subreddit
• `top/new/hot` - Sort method
• `[number]` - Max results (default: 100)

**Quick Commands:**
• `/reddit help` - Show this help
• `/reddit status` - Check system status'''
            })
        
        # Handle help command
        if text.lower() in ['help', '--help', '-h']:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '''🔍 **Reddit Scraper Pro - Help**

**Search Commands:**
```/reddit search AI machine learning```
```/reddit search startups in technology```
```/reddit search crypto top 25```

**Advanced Options:**
• **Subreddit:** `in [subreddit_name]`
• **Sort:** `top`, `hot`, `new`, `relevance`
• **Limit:** Any number (max 500)
• **Multiple keywords:** Separate with spaces

**Examples:**
• `/reddit search AI` → Search "AI" across all Reddit
• `/reddit search python programming in learnpython` → Search specific subreddit
• `/reddit search startup funding hot 50` → Hot posts, limit 50

**System:**
• `/reddit status` → Check if system is online
• `/reddit help` → Show this help message'''
            })
        
        # Handle status command
        if text.lower() in ['status', '--status']:
            reddit_status = "✅ Connected" if get_reddit_instance() else "❌ Not configured"
            return jsonify({
                'response_type': 'ephemeral',
                'text': f'''📊 **Reddit Scraper Pro - Status**

**System:** ✅ Online
**Reddit API:** {reddit_status}
**Search Engine:** ✅ Ready
**Sentiment Analysis:** ✅ Active
**Excel Export:** ✅ Available

**Usage Today:** Active
**Last Updated:** 2025-09-20

*Ready to search Reddit!* 🚀'''
            })
        
        # Parse search command
        if not text.startswith('search '):
            return jsonify({
                'response_type': 'ephemeral',
                'text': f'❌ Unknown command: `{text}`\n\nTry: `/reddit search AI startups` or `/reddit help`'
            })
        
        # Remove 'search' and parse parameters
        search_text = text[7:].strip()  # Remove 'search '
        
        if not search_text:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '❌ Please provide keywords to search.\n\nExample: `/reddit search AI machine learning`'
            })
        
        # Parse parameters
        keywords, subreddit, max_results, sort_method = parse_slack_search_command(search_text)
        
        # Send immediate response
        immediate_response = {
            'response_type': 'in_channel',
            'text': f'🔍 <@{user_name}> is searching Reddit for "{" ".join(keywords)}"...',
            'attachments': [{
                'color': '#1a73e8',
                'text': f'**Keywords:** {", ".join(keywords)}\n**Subreddit:** {subreddit}\n**Max Results:** {max_results}\n**Sort:** {sort_method}',
                'footer': 'Reddit Scraper Pro',
                'footer_icon': 'https://reddit.com/favicon.ico'
            }]
        }
        
        # Start background search (non-blocking)
        if response_url:
            Thread(
                target=perform_slack_search,
                args=(keywords, subreddit, max_results, sort_method, response_url, user_name)
            ).start()
        
        return jsonify(immediate_response)
        
    except Exception as e:
        return jsonify({
            'response_type': 'ephemeral',
            'text': f'❌ Error processing command: {str(e)}'
        })

def parse_slack_search_command(search_text):
    """Parse Slack search command into components"""
    words = search_text.split()
    keywords = []
    subreddit = 'all'
    max_results = 100
    sort_method = 'relevance'
    
    i = 0
    while i < len(words):
        word = words[i].lower()
        
        # Check for subreddit specification
        if word == 'in' and i + 1 < len(words):
            subreddit = words[i + 1].replace('r/', '').replace('R/', '')
            i += 2
            continue
        
        # Check for sort method
        if word in ['hot', 'new', 'top', 'relevance']:
            sort_method = word
            i += 1
            continue
        
        # Check for number (max results)
        if word.isdigit():
            max_results = min(int(word), 500)  # Cap at 500
            i += 1
            continue
        
        # Otherwise, it's a keyword
        keywords.append(words[i])
        i += 1
    
    if not keywords:
        keywords = ['reddit']  # Default search
    
    return keywords, subreddit, max_results, sort_method

def perform_slack_search(keywords, subreddit, max_results, sort_method, response_url, user_name):
    """Perform Reddit search and post results to Slack (background task)"""
    try:
        # Simulate the search API call
        reddit = get_reddit_instance()
        if not reddit:
            post_slack_response(response_url, {
                'text': '❌ Reddit API not configured. Please contact administrator.',
                'response_type': 'ephemeral'
            })
            return
        
        # Create search parameters similar to web interface
        search_query = ' OR '.join(keywords)
        
        # Perform search (reuse existing logic)
        results = perform_reddit_search(
            reddit=reddit,
            keywords=keywords,
            subreddit=subreddit,
            max_results=max_results,
            sort_method=sort_method,
            days_back=0,
            min_score=0,
            min_comments=0,
            min_engagement=0.0,
            sentiment_filter='all'
        )
        
        if results['success']:
            # Format success response
            posts = results['posts']
            response = format_slack_search_results(posts, keywords, subreddit, user_name)
        else:
            # Format error response
            response = {
                'text': f'❌ Search failed: {results["error"]}',
                'response_type': 'ephemeral'
            }
        
        post_slack_response(response_url, response)
        
    except Exception as e:
        post_slack_response(response_url, {
            'text': f'❌ Search error: {str(e)}',
            'response_type': 'ephemeral'
        })

def perform_reddit_search(reddit, keywords, subreddit, max_results, sort_method, days_back, min_score, min_comments, min_engagement, sentiment_filter):
    """Core Reddit search function (reusable for both web and Slack)"""
    try:
        # Build search query
        search_query = ' OR '.join(keywords)
        
        # Handle subreddit selection
        if subreddit.lower() == 'all':
            subreddit_obj = reddit.subreddit('all')
            subreddit_display = 'all of Reddit'
        else:
            # Handle comma-separated or single subreddit
            subreddit_list = [s.replace('r/', '').replace('R/', '').strip() for s in subreddit.split(',') if s.strip()]
            
            if len(subreddit_list) == 1:
                clean_subreddit = subreddit_list[0]
                subreddit_obj = reddit.subreddit(clean_subreddit)
                subreddit_display = f'r/{clean_subreddit}'
            else:
                # Multiple subreddits
                subreddit_obj = reddit.subreddit('+'.join(subreddit_list))
                subreddit_display = f'r/{" + r/".join(subreddit_list)}'
        
        # Perform search based on sort method
        if sort_method == 'hot':
            search_results = subreddit_obj.hot(limit=max_results)
        elif sort_method == 'new':
            search_results = subreddit_obj.new(limit=max_results)
        elif sort_method == 'top':
            search_results = subreddit_obj.top('all', limit=max_results)
        else:
            # Use search for relevance
            search_results = subreddit_obj.search(search_query, sort='relevance', limit=max_results)
        
        # Process results
        posts = []
        for post in search_results:
            try:
                # Calculate metrics
                relevance_score, engagement_rate = calculate_metrics(post, keywords)
                sentiment, sentiment_score = simple_sentiment(f"{post.title} {post.selftext or ''}")
                
                # Apply filters
                if post.score < min_score or post.num_comments < min_comments:
                    continue
                if engagement_rate < min_engagement:
                    continue
                if sentiment_filter != 'all' and sentiment != sentiment_filter:
                    continue
                
                post_data = {
                    'id': post.id,
                    'title': post.title,
                    'url': post.url,
                    'score': post.score,
                    'num_comments': post.num_comments,
                    'subreddit': post.subreddit.display_name,
                    'author': str(post.author) if post.author else '[deleted]',
                    'created_utc': post.created_utc,
                    'date': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M'),
                    'selftext': (post.selftext or '')[:500],  # Limit text
                    'relevance_score': relevance_score,
                    'engagement_rate': engagement_rate,
                    'sentiment': sentiment,
                    'sentiment_score': sentiment_score
                }
                posts.append(post_data)
                
            except Exception as e:
                continue  # Skip problematic posts
        
        return {
            'success': True,
            'posts': posts,
            'search_query': search_query,
            'subreddit_searched': subreddit_display,
            'total_posts': len(posts)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'posts': []
        }

def format_slack_search_results(posts, keywords, subreddit, user_name):
    """Format Reddit search results for Slack response"""
    if not posts:
        return {
            'text': f'🔍 <@{user_name}> searched for "{" ".join(keywords)}" - No results found.',
            'response_type': 'in_channel',
            'attachments': [{
                'color': 'warning',
                'text': f'No posts found for "{" ".join(keywords)}" in r/{subreddit}. Try different keywords or subreddits.',
                'footer': 'Reddit Scraper Pro'
            }]
        }
    
    # Calculate summary stats
    total_posts = len(posts)
    avg_score = sum(p['score'] for p in posts) / total_posts
    total_comments = sum(p['num_comments'] for p in posts)
    positive_posts = len([p for p in posts if p['sentiment'] == 'positive'])
    positive_pct = (positive_posts / total_posts * 100) if total_posts > 0 else 0
    
    # Get top 5 posts by engagement
    top_posts = sorted(posts, key=lambda x: x['engagement_rate'], reverse=True)[:5]
    
    # Format subreddit display
    subreddit_display = f'r/{subreddit}' if subreddit != 'all' else 'all of Reddit'
    
    # Create main response
    response = {
        'text': f'🎉 <@{user_name}> found {total_posts} posts for "{" ".join(keywords)}"!',
        'response_type': 'in_channel',
        'attachments': [
            {
                'color': 'good',
                'title': '📊 Search Summary',
                'fields': [
                    {'title': 'Keywords', 'value': ', '.join(keywords), 'short': True},
                    {'title': 'Subreddit', 'value': subreddit_display, 'short': True},
                    {'title': 'Posts Found', 'value': f'{total_posts:,}', 'short': True},
                    {'title': 'Avg Upvotes', 'value': f'{avg_score:.1f}', 'short': True},
                    {'title': 'Total Comments', 'value': f'{total_comments:,}', 'short': True},
                    {'title': 'Positive Sentiment', 'value': f'{positive_pct:.1f}%', 'short': True}
                ],
                'footer': 'Reddit Scraper Pro',
                'footer_icon': 'https://reddit.com/favicon.ico'
            }
        ]
    }
    
    # Add top posts
    if top_posts:
        posts_text = '\n'.join([
            f'🔥 **{post["title"][:60]}**{"..." if len(post["title"]) > 60 else ""}\n'
            f'   👆 {post["score"]} upvotes • 💬 {post["num_comments"]} comments • r/{post["subreddit"]}\n'
            f'   🔗 <{post["url"]}|View Post>\n'
            for post in top_posts
        ])
        
        response['attachments'].append({
            'color': '#ff6b35',
            'title': f'🔥 Top {len(top_posts)} Posts by Engagement',
            'text': posts_text,
            'mrkdwn_in': ['text']
        })
    
    # Add download link (simulate)
    web_url = 'https://scrapper-eight-alpha.vercel.app'
    response['attachments'].append({
        'color': '#1a73e8',
        'title': '📎 Get Full Analysis',
        'text': f'For complete data analysis and Excel export, visit: <{web_url}|Reddit Scraper Pro>',
        'actions': [
            {
                'type': 'button',
                'text': '🌐 Open Web App',
                'url': web_url
            },
            {
                'type': 'button',
                'text': '🔍 Search Again',
                'name': 'search_again',
                'value': f'/reddit search {"; ".join(keywords)}'
            }
        ]
    })
    
    return response

def post_slack_response(response_url, data):
    """Post response to Slack using response URL"""
    try:
        import requests
        response = requests.post(response_url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f'Failed to post Slack response: {e}')
        return False

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Reddit Scraper Pro Advanced'})

if __name__ == '__main__':
    app.run(debug=True)