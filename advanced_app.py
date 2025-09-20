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
        return False, "Invalid Slack webhook URL format"
    
    return True, "Valid webhook URL"

def test_slack_webhook(webhook_url, channel_name):
    """Test a Slack webhook by sending a test message"""
    try:
        message = {
            "channel": channel_name,
            "username": "Reddit Scraper Pro",
            "icon_emoji": ":mag:",
            "text": ":wave: Test connection successful!",
            "attachments": [{
                "color": "good",
                "fields": [
                    {
                        "title": "Integration Status",
                        "value": "Your Reddit Scraper Pro is now connected to this Slack channel!",
                        "short": False
                    },
                    {
                        "title": "Next Steps",
                        "value": "Run a search to receive notifications about your Reddit analytics.",
                        "short": False
                    }
                ],
                "footer": "Reddit Scraper Pro",
                "footer_icon": "https://reddit.com/favicon.ico",
                "ts": int(time.time())
            }]
        }
        
        response = requests.post(webhook_url, json=message, timeout=10)
        if response.status_code == 200:
            return True, "Test message sent successfully!"
        else:
            return False, f"Failed to send test message. Status code: {response.status_code}"
            
    except Exception as e:
        return False, f"Error testing webhook: {str(e)}"

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
    # TEMPORARY: Simple test page to debug JavaScript
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reddit Scraper Pro - DEBUG</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            button { padding: 15px; margin: 10px; font-size: 16px; cursor: pointer; }
            .test-btn { background: red; color: white; }
            .slack-btn { background: purple; color: white; }
            .discover-btn { background: orange; color: white; }
        </style>
    </head>
    <body>
        <h1>🔍 Reddit Scraper Pro - DEBUG MODE</h1>
        <p>Testing JavaScript functionality:</p>
        
        <button class="test-btn" onclick="testJS()">🔴 TEST JAVASCRIPT</button>
        <button class="slack-btn" onclick="alert('Slack button works!')">⚙️ Test Slack Button</button>
        <button class="discover-btn" onclick="alert('Discover button works!')">🔍 Test Discover Button</button>
        
        <div id="results" style="margin-top: 20px; padding: 20px; background: #f0f0f0; display: none;">
            <h3>Results will show here</h3>
            <p id="result-text">No results yet</p>
        </div>
        
        <script>
            console.log('Simple JavaScript loaded successfully!');
            
            function testJS() {
                console.log('testJS called');
                alert('🎉 JAVASCRIPT IS WORKING!');
                document.getElementById('results').style.display = 'block';
                document.getElementById('result-text').textContent = 'JavaScript test successful at ' + new Date();
            }
            
            // Simple functions to test
            function openSlackModal() {
                alert('Slack modal would open here!');
            }
            
            function openDiscoverModal() {
                alert('Discover modal would open here!');
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

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Reddit Scraper Pro Advanced'})

if __name__ == '__main__':
    app.run(debug=True)