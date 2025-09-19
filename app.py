#!/usr/bin/env python3
"""
Simple Flask App for Vercel Deployment
Reddit Scraper Web Interface
"""

from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import praw
from datetime import datetime, timedelta
import tempfile
import io
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

# Initialize Reddit API
def get_reddit_instance():
    # Clean and validate environment variables
    client_id = os.getenv('REDDIT_CLIENT_ID', '').strip()
    client_secret = os.getenv('REDDIT_CLIENT_SECRET', '').strip()
    user_agent = os.getenv('REDDIT_USER_AGENT', 'RedditScraper/1.0').strip()
    
    # Ensure user agent is properly formatted
    if not user_agent or '\n' in user_agent:
        user_agent = 'RedditScraper/1.0 by user'
    
    if not client_id or not client_secret:
        raise ValueError("Reddit API credentials not found in environment variables")
    
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )

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
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #1a73e8; text-align: center; }
            .form-group { margin: 20px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { background: #1a73e8; color: white; padding: 12px 30px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            button:hover { background: #1557b0; }
            .results { margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 4px; }
            #loading { display: none; text-align: center; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Reddit Scraper Pro</h1>
            <p>Search Reddit posts with advanced filtering and export to JSON.</p>
            
            <form id="searchForm">
                <div class="form-group">
                    <label for="keywords">Keywords (space-separated):</label>
                    <input type="text" id="keywords" name="keywords" placeholder="AI machine learning" required>
                </div>
                
                <div class="form-group">
                    <label for="subreddit">Subreddit (optional):</label>
                    <input type="text" id="subreddit" name="subreddit" placeholder="all" value="all">
                </div>
                
                <div class="form-group">
                    <label for="limit">Max Results:</label>
                    <select id="limit" name="limit">
                        <option value="25">25</option>
                        <option value="50" selected>50</option>
                        <option value="100">100</option>
                        <option value="250">250</option>
                    </select>
                </div>
                
                <button type="submit">🔍 Search Reddit</button>
            </form>
            
            <div id="loading">
                <p>🔄 Searching Reddit... This may take a few moments.</p>
            </div>
            
            <div id="results" class="results" style="display: none;">
                <h3>Results</h3>
                <div id="resultContent"></div>
                <button id="downloadBtn" style="display: none;">📥 Download JSON</button>
            </div>
        </div>
        
        <script>
            document.getElementById('searchForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const loading = document.getElementById('loading');
                const results = document.getElementById('results');
                const resultContent = document.getElementById('resultContent');
                const downloadBtn = document.getElementById('downloadBtn');
                
                loading.style.display = 'block';
                results.style.display = 'none';
                downloadBtn.style.display = 'none';
                
                const formData = new FormData(this);
                const params = new URLSearchParams(formData);
                
                try {
                    const response = await fetch('/api/search?' + params.toString());
                    const data = await response.json();
                    
                    loading.style.display = 'none';
                    results.style.display = 'block';
                    
                    if (data.success) {
                        resultContent.innerHTML = `
                            <p><strong>✅ Found ${data.total_posts} posts</strong></p>
                            <p>Search time: ${data.search_time}</p>
                            <ul>
                                ${data.posts.slice(0, 5).map(post => 
                                    `<li><a href="${post.url}" target="_blank">${post.title}</a> 
                                     (${post.score} points, ${post.subreddit})</li>`
                                ).join('')}
                            </ul>
                            ${data.posts.length > 5 ? `<p>... and ${data.posts.length - 5} more posts</p>` : ''}
                        `;
                        downloadBtn.style.display = 'inline-block';
                        downloadBtn.onclick = () => downloadJSON(data.posts, data.search_query);
                    } else {
                        resultContent.innerHTML = `<p style="color: red;">❌ Error: ${data.error}</p>`;
                    }
                } catch (error) {
                    loading.style.display = 'none';
                    results.style.display = 'block';
                    resultContent.innerHTML = `<p style="color: red;">❌ Network error: ${error.message}</p>`;
                }
            });
            
            function downloadJSON(posts, query) {
                const dataStr = JSON.stringify({
                    search_query: query,
                    total_posts: posts.length,
                    export_time: new Date().toISOString(),
                    posts: posts
                }, null, 2);
                
                const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
                const exportFileDefaultName = `reddit_search_${query.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.json`;
                
                const linkElement = document.createElement('a');
                linkElement.setAttribute('href', dataUri);
                linkElement.setAttribute('download', exportFileDefaultName);
                linkElement.click();
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/search')
def api_search():
    try:
        keywords = request.args.get('keywords', '').strip()
        subreddit = request.args.get('subreddit', 'all').strip()
        limit = min(int(request.args.get('limit', 50)), 250)
        
        if not keywords:
            return jsonify({'success': False, 'error': 'Keywords are required'})
        
        # Initialize Reddit with error handling
        try:
            reddit = get_reddit_instance()
        except ValueError as ve:
            return jsonify({'success': False, 'error': f'Configuration error: {str(ve)}'})
        except Exception as re:
            return jsonify({'success': False, 'error': f'Reddit API error: {str(re)}'})
        
        # Build search query
        search_query = keywords
        if subreddit and subreddit.lower() != 'all':
            subreddit_obj = reddit.subreddit(subreddit)
        else:
            subreddit_obj = reddit.subreddit('all')
        
        # Search posts
        start_time = datetime.now()
        posts = []
        
        for post in subreddit_obj.search(search_query, sort='relevance', limit=limit):
            posts.append({
                'title': post.title,
                'subreddit': str(post.subreddit),
                'author': str(post.author) if post.author else '[deleted]',
                'score': post.score,
                'upvote_ratio': post.upvote_ratio,
                'num_comments': post.num_comments,
                'created_utc': datetime.fromtimestamp(post.created_utc).isoformat(),
                'url': f"https://reddit.com{post.permalink}",
                'selftext': post.selftext[:500] + '...' if len(post.selftext) > 500 else post.selftext,
                'is_nsfw': post.over_18,
                'post_id': post.id
            })
        
        search_time = (datetime.now() - start_time).total_seconds()
        
        return jsonify({
            'success': True,
            'total_posts': len(posts),
            'search_query': search_query,
            'search_time': f"{search_time:.2f} seconds",
            'posts': posts
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Reddit Scraper Pro'})

if __name__ == '__main__':
    app.run(debug=True)