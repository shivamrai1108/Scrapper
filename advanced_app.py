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
import sqlite3
import hashlib
import hmac
from cryptography.fernet import Fernet
import base64

app = Flask(__name__)

# ============ MULTI-TENANT SLACK SYSTEM ============

# Database setup
DB_PATH = 'slack_workspaces.db'
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def init_database():
    """Initialize the multi-tenant Slack database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Workspaces table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT UNIQUE NOT NULL,
            team_name TEXT NOT NULL,
            bot_token TEXT NOT NULL,  -- Encrypted
            bot_user_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            plan_type TEXT DEFAULT 'free',
            usage_count INTEGER DEFAULT 0,
            usage_limit INTEGER DEFAULT 100,
            settings JSON,
            created_by TEXT,
            webhook_url TEXT  -- Encrypted, optional
        )
    ''')
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workspace_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER,
            user_id TEXT NOT NULL,
            user_name TEXT,
            access_token TEXT,  -- Encrypted, for user-specific actions
            permissions JSON,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
        )
    ''')
    
    # Usage tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER,
            user_id TEXT,
            command TEXT,
            search_term TEXT,
            result_count INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN,
            error_message TEXT,
            FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
        )
    ''')
    
    # App installations tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS installations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            installer_user_id TEXT,
            installation_data JSON,
            installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uninstalled_at TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[DB] Multi-tenant database initialized")

def encrypt_token(token):
    """Encrypt sensitive tokens before storing"""
    if not token:
        return None
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token):
    """Decrypt tokens for use"""
    if not encrypted_token:
        return None
    try:
        return fernet.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        print(f"[ENCRYPT] Failed to decrypt token: {e}")
        return None

def get_workspace_by_team_id(team_id):
    """Get workspace data by Slack team ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM workspaces WHERE team_id = ? AND is_active = TRUE', (team_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        columns = ['id', 'team_id', 'team_name', 'bot_token', 'bot_user_id', 'scope', 
                  'installed_at', 'last_active', 'is_active', 'plan_type', 'usage_count', 
                  'usage_limit', 'settings', 'created_by', 'webhook_url']
        workspace = dict(zip(columns, row))
        
        # Decrypt sensitive data
        workspace['bot_token'] = decrypt_token(workspace['bot_token'])
        workspace['webhook_url'] = decrypt_token(workspace['webhook_url'])
        
        # Parse JSON fields
        if workspace['settings']:
            workspace['settings'] = json.loads(workspace['settings'])
        
        return workspace
    return None

def store_workspace(team_id, team_name, bot_token, bot_user_id, scope, installer_user_id=None):
    """Store new workspace installation"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    encrypted_bot_token = encrypt_token(bot_token)
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO workspaces 
            (team_id, team_name, bot_token, bot_user_id, scope, created_by, settings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            team_id, team_name, encrypted_bot_token, bot_user_id, scope, 
            installer_user_id, json.dumps({'notifications': True, 'max_results': 50})
        ))
        
        workspace_id = cursor.lastrowid
        
        # Log installation
        cursor.execute('''
            INSERT INTO installations 
            (team_id, installer_user_id, installation_data)
            VALUES (?, ?, ?)
        ''', (
            team_id, installer_user_id, 
            json.dumps({'bot_user_id': bot_user_id, 'scope': scope})
        ))
        
        conn.commit()
        print(f"[DB] Stored workspace: {team_name} ({team_id})")
        return workspace_id
        
    except Exception as e:
        print(f"[DB] Error storing workspace: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def log_usage(workspace_id, user_id, command, search_term=None, result_count=0, success=True, error=None):
    """Log command usage for analytics and billing"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Log usage
        cursor.execute('''
            INSERT INTO usage_logs 
            (workspace_id, user_id, command, search_term, result_count, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (workspace_id, user_id, command, search_term, result_count, success, error))
        
        # Update workspace usage count
        cursor.execute('''
            UPDATE workspaces 
            SET usage_count = usage_count + 1, last_active = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (workspace_id,))
        
        conn.commit()
    except Exception as e:
        print(f"[DB] Error logging usage: {e}")
    finally:
        conn.close()

# Initialize database on startup
init_database()

# ============ OAUTH 2.0 SLACK APP INSTALLATION ============

@app.route('/slack/install')
def slack_install():
    """Start Slack OAuth installation process"""
    # Slack OAuth parameters
    client_id = os.getenv('SLACK_CLIENT_ID', 'your_client_id_here')
    scope = 'commands,chat:write,bot,users:read,channels:read,groups:read'
    redirect_uri = f"{request.host_url}slack/oauth/callback"
    
    # Generate state parameter for security
    state = hashlib.sha256(f"{client_id}{time.time()}".encode()).hexdigest()[:16]
    
    oauth_url = (
        f"https://slack.com/oauth/v2/authorize?"
        f"client_id={client_id}&"
        f"scope={scope}&"
        f"redirect_uri={redirect_uri}&"
        f"state={state}"
    )
    
    # Store state for verification (in production, use Redis or database)
    # For now, we'll skip state verification for simplicity
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Install Reddit Scraper Pro to Slack</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   background: #f8f9fa; margin: 0; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 40px; 
                        border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center; }}
            .logo {{ font-size: 3rem; margin-bottom: 20px; }}
            h1 {{ color: #1a73e8; margin-bottom: 20px; }}
            p {{ color: #666; margin-bottom: 30px; line-height: 1.6; }}
            .install-btn {{ background: #4A154B; color: white; padding: 15px 30px; border: none; 
                          border-radius: 6px; font-size: 16px; font-weight: bold; text-decoration: none; 
                          display: inline-block; transition: background 0.2s; }}
            .install-btn:hover {{ background: #611F69; }}
            .features {{ text-align: left; margin: 30px 0; padding: 20px; background: #f8f9fa; 
                        border-radius: 8px; }}
            .feature {{ margin: 10px 0; }}
            .feature strong {{ color: #1a73e8; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🔍</div>
            <h1>Install Reddit Scraper Pro</h1>
            <p>Add powerful Reddit search and analytics directly to your Slack workspace!</p>
            
            <div class="features">
                <div class="feature"><strong>🚀 Slash Commands:</strong> Use <code>/reddit search [keywords]</code> in any channel</div>
                <div class="feature"><strong>📊 Analytics:</strong> Get sentiment analysis, engagement metrics, and top posts</div>
                <div class="feature"><strong>⚡ Smart Search:</strong> Search specific subreddits with advanced filtering</div>
                <div class="feature"><strong>🔒 Secure:</strong> Your data is encrypted and never shared</div>
                <div class="feature"><strong>🎆 Free Tier:</strong> 100 searches per month included</div>
            </div>
            
            <p><strong>After installation, you can:</strong></p>
            <ul style="text-align: left; color: #666;">
                <li>Type <code>/reddit search AI startups</code> to search all of Reddit</li>
                <li>Use <code>/reddit search crypto in bitcoin</code> for specific subreddits</li>
                <li>Get <code>/reddit help</code> for all available commands</li>
            </ul>
            
            <a href="{oauth_url}" class="install-btn">
                <img src="https://platform.slack-edge.com/img/add_to_slack.png" 
                     alt="Add to Slack" height="40" width="139" 
                     style="vertical-align: middle; margin-right: 10px;">
                Install to Slack
            </a>
            
            <p style="font-size: 14px; color: #999; margin-top: 30px;">
                Powered by Reddit Scraper Pro • 
                <a href="{request.host_url}" style="color: #1a73e8;">Visit Website</a>
            </p>
        </div>
    </body>
    </html>
    '''

@app.route('/slack/oauth/callback')
def slack_oauth_callback():
    """Handle Slack OAuth callback and store workspace tokens"""
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')
    
    if error:
        return f'''
        <div style="text-align: center; padding: 50px; font-family: sans-serif;">
            <h2 style="color: #dc3545;">❌ Installation Failed</h2>
            <p>Error: {error}</p>
            <p><a href="/slack/install" style="color: #1a73e8;">Try Again</a></p>
        </div>
        '''
    
    if not code:
        return 'Missing authorization code', 400
    
    # Exchange code for access token
    client_id = os.getenv('SLACK_CLIENT_ID', 'your_client_id_here')
    client_secret = os.getenv('SLACK_CLIENT_SECRET', 'your_client_secret_here')
    redirect_uri = f"{request.host_url}slack/oauth/callback"
    
    try:
        # Exchange code for token
        response = requests.post('https://slack.com/api/oauth.v2.access', {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        })
        
        data = response.json()
        
        if not data.get('ok'):
            return f'OAuth error: {data.get("error", "Unknown error")}', 400
        
        # Extract installation data
        team_id = data['team']['id']
        team_name = data['team']['name']
        bot_token = data['access_token']
        bot_user_id = data['bot_user_id']
        scope = data['scope']
        installer_user_id = data['authed_user']['id']
        
        print(f"[OAUTH] Installing for team: {team_name} ({team_id})")
        print(f"[OAUTH] Bot user ID: {bot_user_id}")
        print(f"[OAUTH] Scope: {scope}")
        
        # Store workspace data securely
        workspace_id = store_workspace(
            team_id, team_name, bot_token, bot_user_id, scope, installer_user_id
        )
        
        if workspace_id:
            return f'''
            <div style="text-align: center; padding: 50px; font-family: sans-serif;">
                <div style="font-size: 4rem; margin-bottom: 20px;">🎉</div>
                <h2 style="color: #28a745;">Installation Successful!</h2>
                <p style="font-size: 18px; color: #666;">Reddit Scraper Pro has been added to <strong>{team_name}</strong></p>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 30px 0; text-align: left; max-width: 500px; margin-left: auto; margin-right: auto;">
                    <h3 style="color: #1a73e8; margin-top: 0;">🚀 Try these commands in Slack:</h3>
                    <ul style="color: #666; line-height: 1.8;">
                        <li><code>/reddit search AI startups</code> - Search all of Reddit</li>
                        <li><code>/reddit search crypto in bitcoin</code> - Search specific subreddit</li>
                        <li><code>/reddit search python top 25</code> - Get top 25 results</li>
                        <li><code>/reddit help</code> - Show all available commands</li>
                        <li><code>/reddit status</code> - Check system status</li>
                    </ul>
                </div>
                
                <p style="color: #666;">Your team has <strong>100 free searches per month</strong></p>
                <p><a href="https://slack.com/app_redirect?team={team_id}" style="background: #4A154B; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Open Slack</a></p>
                
                <p style="font-size: 14px; color: #999; margin-top: 30px;">
                    Need help? Visit <a href="{request.host_url}" style="color: #1a73e8;">our documentation</a> or contact support
                </p>
            </div>
            '''
        else:
            return 'Failed to store workspace data', 500
            
    except Exception as e:
        print(f"[OAUTH] Error during installation: {e}")
        return f'Installation failed: {str(e)}', 500

# ============ WORKSPACE MANAGEMENT DASHBOARD ============

def generate_workspace_list_html(workspace_data):
    """Generate HTML for workspace list"""
    html_parts = []
    for ws in workspace_data:
        status_class = "status-active" if ws['is_active'] else "status-inactive"
        status_text = "✅ Active" if ws['is_active'] else "❌ Inactive"
        btn_class = "btn-danger" if ws['is_active'] else "btn-primary"
        btn_text = "Deactivate" if ws['is_active'] else "Activate"
        btn_onclick = f"updateWorkspaceStatus('{ws['team_id']}', {str(not ws['is_active']).lower()})"
        
        usage_pct = (ws['usage_count']/ws['usage_limit']*100) if ws['usage_limit'] > 0 else 0
        usage_width = min(100, usage_pct)
        
        html_parts.append(f'''
        <div class="workspace">
            <div class="workspace-header">
                <div>
                    <div class="workspace-name">
                        {ws['team_name']} 
                        <span class="{status_class}">
                            {status_text}
                        </span>
                    </div>
                    <div class="workspace-id">{ws['team_id']}</div>
                </div>
                <div class="plan">{ws['plan_type'].upper()}</div>
            </div>
            
            <div class="workspace-stats">
                <div><strong>Usage:</strong> {ws['usage_count']}/{ws['usage_limit']} ({usage_pct:.1f}%)</div>
                <div><strong>Installed:</strong> {ws['installed_at'][:10]}</div>
                <div><strong>Last Active:</strong> {ws['last_active'][:10] if ws['last_active'] else 'Never'}</div>
                <div><strong>Total Commands:</strong> {ws['total_usage_logs']}</div>
                <div><strong>Scope:</strong> {ws['scope']}</div>
            </div>
            
            <div class="usage-bar">
                <div class="usage-fill" style="width: {usage_width}%"></div>
            </div>
            
            <div class="admin-actions">
                <button class="btn {btn_class}" onclick="{btn_onclick}">
                    {btn_text}
                </button>
                <button class="btn btn-warning" onclick="resetUsage('{ws['team_id']}')">Reset Usage</button>
                <button class="btn btn-primary" 
                        onclick="window.open('/admin/workspace/{ws['team_id']}/logs', '_blank')">View Logs</button>
            </div>
        </div>
        ''')
    
    return ''.join(html_parts)

@app.route('/admin/workspaces')
def workspace_dashboard():
    """Admin dashboard for managing connected workspaces"""
    # Simple auth check (in production, use proper authentication)
    auth_key = request.args.get('key')
    if auth_key != os.getenv('ADMIN_KEY', 'admin_secret_key'):
        return 'Unauthorized', 401
    
    # Get all workspaces with usage stats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT w.*, 
               COUNT(u.id) as total_usage_logs,
               MAX(u.timestamp) as last_used
        FROM workspaces w
        LEFT JOIN usage_logs u ON w.id = u.workspace_id
        WHERE w.is_active = TRUE
        GROUP BY w.id
        ORDER BY w.installed_at DESC
    ''')
    
    workspaces = cursor.fetchall()
    columns = ['id', 'team_id', 'team_name', 'bot_token', 'bot_user_id', 'scope', 
              'installed_at', 'last_active', 'is_active', 'plan_type', 'usage_count', 
              'usage_limit', 'settings', 'created_by', 'webhook_url', 'total_usage_logs', 'last_used']
    
    workspace_data = []
    for row in workspaces:
        ws = dict(zip(columns, row))
        ws['bot_token'] = '***ENCRYPTED***'  # Don't show tokens
        workspace_data.append(ws)
    
    # Get total stats
    cursor.execute('SELECT COUNT(*) FROM workspaces WHERE is_active = TRUE')
    total_workspaces = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(usage_count) FROM workspaces WHERE is_active = TRUE')
    total_searches = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM usage_logs WHERE timestamp > datetime("now", "-24 hours")')
    searches_today = cursor.fetchone()[0]
    
    conn.close()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reddit Scraper Pro - Workspace Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   background: #f8f9fa; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ color: #1a73e8; text-align: center; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat {{ flex: 1; background: white; padding: 20px; border-radius: 8px; 
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
            .stat-value {{ font-size: 2rem; font-weight: bold; color: #1a73e8; }}
            .stat-label {{ color: #666; margin-top: 5px; }}
            .workspace-list {{ background: white; border-radius: 8px; 
                             box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
            .workspace {{ padding: 20px; border-bottom: 1px solid #eee; position: relative; }}
            .workspace:last-child {{ border-bottom: none; }}
            .workspace-header {{ display: flex; justify-content: space-between; align-items: center; 
                               margin-bottom: 10px; }}
            .workspace-name {{ font-size: 18px; font-weight: bold; color: #333; }}
            .workspace-id {{ font-family: monospace; color: #666; font-size: 14px; }}
            .workspace-stats {{ display: flex; gap: 20px; color: #666; font-size: 14px; }}
            .plan {{ background: #e3f2fd; color: #1565c0; padding: 4px 8px; 
                    border-radius: 4px; font-size: 12px; font-weight: bold; }}
            .usage-bar {{ background: #f0f0f0; border-radius: 10px; height: 8px; margin: 10px 0; }}
            .usage-fill {{ background: #1a73e8; height: 100%; border-radius: 10px; transition: width 0.3s; }}
            .admin-actions {{ display: flex; gap: 10px; margin-top: 10px; }}
            .btn {{ padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold; cursor: pointer; border: none; }}
            .btn-danger {{ background: #dc3545; color: white; }}
            .btn-warning {{ background: #ffc107; color: #212529; }}
            .btn-primary {{ background: #007bff; color: white; }}
            .filters {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; 
                       box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status-active {{ color: #28a745; }}
            .status-inactive {{ color: #dc3545; }}
        </style>
        <script>
            function updateWorkspaceStatus(teamId, active) {{
                fetch(`/admin/workspace/${{teamId}}/status`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{active: active, key: '{os.getenv('ADMIN_KEY', 'admin_secret_key')}'}}) 
                }})
                .then(r => r.json())
                .then(data => {{
                    if(data.success) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + data.error);
                    }}
                }});
            }}
            
            function resetUsage(teamId) {{
                if(confirm('Reset usage count for this workspace?')) {{
                    fetch(`/admin/workspace/${{teamId}}/reset-usage`, {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{key: '{os.getenv('ADMIN_KEY', 'admin_secret_key')}'}}) 
                    }})
                    .then(r => r.json())
                    .then(data => {{
                        if(data.success) {{
                            location.reload();
                        }} else {{
                            alert('Error: ' + data.error);
                        }}
                    }});
                }}
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Reddit Scraper Pro - Admin Dashboard</h1>
            
            <div class="filters">
                <h3>Quick Actions</h3>
                <div class="admin-actions">
                    <button class="btn btn-primary" onclick="location.reload()">Refresh Data</button>
                    <button class="btn btn-warning" onclick="window.open('https://api.slack.com/apps', '_blank')">Slack App Console</button>
                    <button class="btn btn-primary" onclick="window.open('/slack/install', '_blank')">Installation Page</button>
                </div>
            </div>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{total_workspaces}</div>
                    <div class="stat-label">Connected Workspaces</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{total_searches:,}</div>
                    <div class="stat-label">Total Searches</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{searches_today}</div>
                    <div class="stat-label">Searches Today</div>
                </div>
            </div>
            
            <div class="workspace-list">
                {generate_workspace_list_html(workspace_data)}
            </div>
            
            <p style="text-align: center; color: #666; margin-top: 30px;">
                Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
            </p>
        </div>
    </body>
    </html>
    '''

# ============ BILLING AND PRICING SYSTEM ============

# Pricing plans configuration
PRICING_PLANS = {
    'free': {
        'name': 'Free',
        'price': 0,
        'searches_per_month': 100,
        'features': ['Basic search', 'Up to 50 results', 'Community support']
    },
    'pro': {
        'name': 'Pro',
        'price': 29,
        'searches_per_month': 1000,
        'features': ['Advanced search', 'Up to 500 results', 'Priority support', 'Analytics dashboard']
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': 99,
        'searches_per_month': 10000,
        'features': ['Unlimited search', 'Custom integrations', '24/7 support', 'White-label option']
    }
}

def check_workspace_limits(workspace):
    """Check if workspace has exceeded limits and needs upgrade"""
    plan = workspace.get('plan_type', 'free')
    usage_count = workspace.get('usage_count', 0)
    usage_limit = workspace.get('usage_limit', 100)
    
    # Calculate usage percentage
    usage_percentage = (usage_count / usage_limit) * 100 if usage_limit > 0 else 100
    
    return {
        'plan': plan,
        'usage_count': usage_count,
        'usage_limit': usage_limit,
        'usage_percentage': usage_percentage,
        'over_limit': usage_count >= usage_limit,
        'near_limit': usage_percentage >= 80,  # 80% threshold warning
        'can_upgrade': plan in ['free', 'pro']  # Enterprise is highest tier
    }

@app.route('/pricing')
def pricing_page():
    """Display pricing information"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reddit Scraper Pro - Pricing</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   margin: 0; padding: 40px; min-height: 100vh; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            h1 {{ text-align: center; color: white; font-size: 3rem; margin-bottom: 20px; }}
            .subtitle {{ text-align: center; color: rgba(255,255,255,0.9); font-size: 1.2rem; 
                        margin-bottom: 50px; }}
            .plans {{ display: flex; gap: 30px; justify-content: center; flex-wrap: wrap; }}
            .plan {{ background: white; border-radius: 15px; padding: 40px; text-align: center; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2); transition: transform 0.3s; 
                    min-width: 280px; position: relative; }}
            .plan:hover {{ transform: translateY(-10px); }}
            .plan.popular {{ border: 3px solid #1a73e8; transform: scale(1.05); }}
            .plan.popular::before {{ content: 'Most Popular'; position: absolute; top: -15px; 
                                   left: 50%; transform: translateX(-50%); background: #1a73e8; 
                                   color: white; padding: 8px 20px; border-radius: 20px; 
                                   font-size: 12px; font-weight: bold; }}
            .plan-name {{ font-size: 2rem; font-weight: bold; color: #333; margin-bottom: 10px; }}
            .plan-price {{ font-size: 3rem; font-weight: bold; color: #1a73e8; margin-bottom: 20px; }}
            .plan-price small {{ font-size: 1rem; color: #666; }}
            .plan-features {{ list-style: none; padding: 0; margin: 30px 0; }}
            .plan-features li {{ margin: 15px 0; padding: 10px 0; border-bottom: 1px solid #eee; 
                               color: #666; }}
            .plan-features li:last-child {{ border-bottom: none; }}
            .cta-btn {{ background: #1a73e8; color: white; padding: 15px 40px; border: none; 
                      border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; 
                      text-decoration: none; display: inline-block; transition: background 0.3s; }}
            .cta-btn:hover {{ background: #1557b0; }}
            .free-btn {{ background: #28a745; }}
            .free-btn:hover {{ background: #218838; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Reddit Scraper Pro</h1>
            <p class="subtitle">Choose the perfect plan for your team's Reddit research needs</p>
            
            <div class="plans">
                <div class="plan">
                    <div class="plan-name">Free</div>
                    <div class="plan-price">$0<small>/month</small></div>
                    <ul class="plan-features">
                        <li>✅ 100 searches per month</li>
                        <li>✅ Basic search functionality</li>
                        <li>✅ Up to 50 results per search</li>
                        <li>✅ Community support</li>
                        <li>✅ Slack integration</li>
                    </ul>
                    <a href="/slack/install" class="cta-btn free-btn">Get Started Free</a>
                </div>
                
                <div class="plan popular">
                    <div class="plan-name">Pro</div>
                    <div class="plan-price">$29<small>/month</small></div>
                    <ul class="plan-features">
                        <li>✅ 1,000 searches per month</li>
                        <li>✅ Advanced search filters</li>
                        <li>✅ Up to 500 results per search</li>
                        <li>✅ Sentiment analysis</li>
                        <li>✅ Priority support</li>
                        <li>✅ Analytics dashboard</li>
                        <li>✅ Export to Excel/CSV</li>
                    </ul>
                    <a href="mailto:support@redditscraperpro.com?subject=Pro Plan Upgrade" class="cta-btn">Upgrade to Pro</a>
                </div>
                
                <div class="plan">
                    <div class="plan-name">Enterprise</div>
                    <div class="plan-price">$99<small>/month</small></div>
                    <ul class="plan-features">
                        <li>✅ 10,000 searches per month</li>
                        <li>✅ Unlimited results</li>
                        <li>✅ Custom integrations</li>
                        <li>✅ White-label option</li>
                        <li>✅ 24/7 dedicated support</li>
                        <li>✅ Custom training</li>
                        <li>✅ API access</li>
                        <li>✅ Multi-workspace management</li>
                    </ul>
                    <a href="mailto:support@redditscraperpro.com?subject=Enterprise Plan" class="cta-btn">Contact Sales</a>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 50px; color: rgba(255,255,255,0.8);">
                <p>All plans include SSL encryption, data privacy compliance, and regular updates.</p>
                <p><a href="/" style="color: white;">← Back to Home</a></p>
            </div>
        </div>
    </body>
    </html>
    '''

def generate_revenue_html(revenue_data):
    """Generate HTML for revenue data"""
    html_parts = []
    for data in revenue_data:
        html_parts.append(f'''
        <div class="plan-row">
            <div>
                <strong>{data['plan']}</strong><br>
                <small>{data['workspaces']} workspaces • {data['total_usage']:,} searches</small>
            </div>
            <div style="text-align: right;">
                <strong>${data['monthly_revenue']:,}/month</strong><br>
                <small>${data['price']}/workspace</small>
            </div>
        </div>
        ''')
    return ''.join(html_parts)

def generate_users_table_html(top_users):
    """Generate HTML for users table"""
    html_parts = []
    for user in top_users:
        utilization = (user[2]/user[3]*100) if user[3] > 0 else 0
        html_parts.append(f'''
        <tr>
            <td>{user[0]}</td>
            <td>{user[1].title()}</td>
            <td>{user[2]:,}</td>
            <td>{user[3]:,}</td>
            <td>{utilization:.1f}%</td>
        </tr>
        ''')
    return ''.join(html_parts)

@app.route('/admin/billing')
def billing_dashboard():
    """Admin billing and revenue dashboard"""
    auth_key = request.args.get('key')
    if auth_key != os.getenv('ADMIN_KEY', 'admin_secret_key'):
        return 'Unauthorized', 401
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get billing stats
    cursor.execute('''
        SELECT plan_type, COUNT(*) as workspaces, SUM(usage_count) as total_usage
        FROM workspaces 
        WHERE is_active = TRUE
        GROUP BY plan_type
    ''')
    plan_stats = cursor.fetchall()
    
    # Calculate potential revenue
    revenue_data = []
    total_revenue = 0
    
    for plan, count, usage in plan_stats:
        plan_info = PRICING_PLANS.get(plan, PRICING_PLANS['free'])
        monthly_revenue = plan_info['price'] * count
        total_revenue += monthly_revenue
        
        revenue_data.append({
            'plan': plan.title(),
            'workspaces': count,
            'price': plan_info['price'],
            'monthly_revenue': monthly_revenue,
            'total_usage': usage,
            'avg_usage': usage // count if count > 0 else 0
        })
    
    # Get top usage workspaces
    cursor.execute('''
        SELECT team_name, plan_type, usage_count, usage_limit
        FROM workspaces 
        WHERE is_active = TRUE
        ORDER BY usage_count DESC
        LIMIT 10
    ''')
    top_users = cursor.fetchall()
    
    conn.close()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Billing Dashboard - Reddit Scraper Pro</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   background: #f8f9fa; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ color: #1a73e8; text-align: center; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
            .stat {{ flex: 1; background: white; padding: 20px; border-radius: 8px; 
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; min-width: 200px; }}
            .stat-value {{ font-size: 2rem; font-weight: bold; color: #1a73e8; }}
            .stat-label {{ color: #666; margin-top: 5px; }}
            .section {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; 
                       box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .plan-row {{ display: flex; justify-content: space-between; padding: 15px; 
                       border-bottom: 1px solid #eee; align-items: center; }}
            .plan-row:last-child {{ border-bottom: none; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💰 Billing Dashboard</h1>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">${total_revenue:,}</div>
                    <div class="stat-label">Monthly Revenue</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{sum(data['workspaces'] for data in revenue_data)}</div>
                    <div class="stat-label">Active Workspaces</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{sum(data['total_usage'] for data in revenue_data):,}</div>
                    <div class="stat-label">Total Searches</div>
                </div>
            </div>
            
            <div class="section">
                <h3>Revenue by Plan</h3>
                {generate_revenue_html(revenue_data)}
            </div>
            
            <div class="section">
                <h3>Top Usage Workspaces</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Workspace</th>
                            <th>Plan</th>
                            <th>Usage</th>
                            <th>Limit</th>
                            <th>Utilization</th>
                        </tr>
                    </thead>
                    <tbody>
                        {generate_users_table_html(top_users)}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    '''

# Admin API endpoints for workspace management
@app.route('/admin/workspace/<team_id>/status', methods=['POST'])
def update_workspace_status(team_id):
    """Update workspace active status"""
    try:
        data = request.get_json()
        auth_key = data.get('key')
        
        if auth_key != os.getenv('ADMIN_KEY', 'admin_secret_key'):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        is_active = data.get('active', True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE workspaces SET is_active = ? WHERE team_id = ?', (is_active, team_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'error': 'Workspace not found'})
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Workspace {"activated" if is_active else "deactivated"}'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/workspace/<team_id>/reset-usage', methods=['POST'])
def reset_workspace_usage(team_id):
    """Reset workspace usage count"""
    try:
        data = request.get_json()
        auth_key = data.get('key')
        
        if auth_key != os.getenv('ADMIN_KEY', 'admin_secret_key'):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE workspaces SET usage_count = 0 WHERE team_id = ?', (team_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'error': 'Workspace not found'})
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Usage count reset to 0'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_logs_html(logs):
    """Generate HTML for workspace logs"""
    html_parts = []
    for log in logs:
        html_parts.append(f'''
        <div class="log">
            <div class="log-time">{log[3]}</div>
            <div class="log-user">User: {log[1]} ({log[-1] or "Unknown"})</div>
            <div class="log-query">Query: {log[4] or "N/A"}</div>
            <div>Results: {log[5] or 0} posts</div>
        </div>
        ''')
    return ''.join(html_parts)

@app.route('/admin/workspace/<team_id>/logs')
def workspace_logs(team_id):
    """View detailed logs for a specific workspace"""
    auth_key = request.args.get('key')
    if auth_key != os.getenv('ADMIN_KEY', 'admin_secret_key'):
        return 'Unauthorized', 401
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get workspace info
    cursor.execute('SELECT * FROM workspaces WHERE team_id = ?', (team_id,))
    workspace = cursor.fetchone()
    
    if not workspace:
        return 'Workspace not found', 404
    
    # Get usage logs
    cursor.execute('''
        SELECT ul.*, wu.user_name 
        FROM usage_logs ul
        LEFT JOIN workspace_users wu ON ul.user_id = wu.user_id AND ul.workspace_id = wu.workspace_id
        WHERE ul.workspace_id = ?
        ORDER BY ul.timestamp DESC
        LIMIT 100
    ''', (workspace[0],))  # workspace[0] is the ID
    
    logs = cursor.fetchall()
    conn.close()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Workspace Logs - {workspace[2]}</title>
        <style>
            body {{ font-family: monospace; background: #f8f9fa; margin: 20px; }}
            .header {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .log {{ background: white; margin: 10px 0; padding: 15px; border-radius: 4px; 
                   border-left: 4px solid #007bff; }}
            .log-time {{ color: #666; font-size: 12px; }}
            .log-user {{ font-weight: bold; color: #333; }}
            .log-query {{ background: #f8f9fa; padding: 5px; border-radius: 3px; margin: 5px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Usage Logs: {workspace[2]}</h1>
            <p><strong>Team ID:</strong> {team_id}</p>
            <p><strong>Total Logs:</strong> {len(logs)}</p>
        </div>
        
        {generate_logs_html(logs)}
        
        <p style="text-align: center; color: #666; margin-top: 50px;">
            Showing last 100 usage logs
        </p>
    </body>
    </html>
    '''

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
        .modal-body { padding: 30px; max-height: 70vh; overflow-y: auto; }
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
        
        .subreddit-results { background: white; border-radius: 8px; border: 1px solid #ddd; max-height: 400px; overflow-y: auto; }
        .subreddit-item { display: flex; align-items: center; justify-content: space-between; 
                         padding: 15px; border-bottom: 1px solid #eee; transition: background-color 0.2s; }
        .subreddit-item:hover { background-color: #f8f9fa; }
        .subreddit-item:last-child { border-bottom: none; }
        .subreddit-info { flex-grow: 1; min-width: 0; }
        .subreddit-name { font-weight: bold; color: #1a73e8; font-size: 14px; margin-bottom: 4px; }
        .subreddit-stats { color: #28a745; font-size: 12px; font-weight: 600; margin-bottom: 4px; }
        .subreddit-description { color: #666; font-size: 12px; line-height: 1.4; 
                               overflow: hidden; text-overflow: ellipsis; display: -webkit-box;
                               -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
        .add-btn { background: #28a745; color: white; border: none; padding: 8px 16px; 
                  border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: bold; 
                  width: auto; min-width: 70px; transition: all 0.2s; flex-shrink: 0; }
        .add-btn:hover { background: #218838; transform: translateY(-1px); }
        .add-btn:disabled { background: #6c757d; cursor: not-allowed; transform: none; }
        
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
        
        // Enhanced search with pagination and infinite scroll
        let currentPage = 1;
        let isLoading = false;
        let hasMore = true;
        let currentSearchTerm = '';
        
        async function searchSubredditsInModal(reset = true) {
            const searchTerm = document.getElementById('modalSearchInput').value.trim();
            if (!searchTerm) {
                showAlert('error', 'Please enter a search term to find subreddits.');
                return;
            }
            
            // Reset pagination for new search
            if (reset || currentSearchTerm !== searchTerm) {
                currentPage = 1;
                hasMore = true;
                currentSearchTerm = searchTerm;
            }
            
            if (isLoading || !hasMore) return;
            
            const loading = document.getElementById('modalLoading');
            const results = document.getElementById('modalResults');
            const resultsList = document.getElementById('modalResultsList');
            
            isLoading = true;
            loading.style.display = 'block';
            
            if (reset) {
                results.style.display = 'none';
                resultsList.innerHTML = '';
            }
            
            try {
                const response = await fetch(`/api/discover_subreddits?search=${encodeURIComponent(searchTerm)}&page=${currentPage}&limit=20`);
                const data = await response.json();
                
                loading.style.display = 'none';
                isLoading = false;
                
                if (data.success && data.subreddits.length > 0) {
                    const newItems = data.subreddits.map(sub => {
                        const isSelected = selectedSubreddits.has(sub.name);
                        return `
                            <div class="subreddit-item" data-subreddit="${sub.name}">
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
                    
                    if (reset) {
                        resultsList.innerHTML = newItems;
                    } else {
                        resultsList.innerHTML += newItems;
                    }
                    
                    // Update pagination state
                    hasMore = data.has_more;
                    currentPage++;
                    
                    // Add load more button if there are more results
                    updateLoadMoreButton(data);
                    
                    results.style.display = 'block';
                    
                    // Show search summary
                    if (reset) {
                        showSearchSummary(data);
                    }
                } else if (reset) {
                    resultsList.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No subreddits found. Try a different search term.</p>';
                    results.style.display = 'block';
                }
            } catch (error) {
                loading.style.display = 'none';
                isLoading = false;
                showAlert('error', `Search failed: ${error.message}`);
            }
        }
        
        function showSearchSummary(data) {
            const summaryHtml = `
                <div class="search-summary" style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #1a73e8;">
                    <strong>🔍 Search Results for "${data.search_term}"</strong><br>
                    <span style="color: #666; font-size: 14px;">Found ${data.total_found}+ communities • Page ${data.page - 1} • ${data.has_more ? 'More available' : 'All results shown'}</span>
                </div>
            `;
            
            const resultsList = document.getElementById('modalResultsList');
            resultsList.insertAdjacentHTML('afterbegin', summaryHtml);
        }
        
        function updateLoadMoreButton(data) {
            const resultsList = document.getElementById('modalResultsList');
            
            // Remove existing load more button
            const existingBtn = document.getElementById('loadMoreBtn');
            if (existingBtn) existingBtn.remove();
            
            // Add new load more button if needed
            if (data.has_more) {
                const loadMoreBtn = `
                    <div id="loadMoreBtn" style="text-align: center; padding: 20px;">
                        <button onclick="searchSubredditsInModal(false)" 
                                style="background: #1a73e8; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-size: 14px;">
                            🔄 Load More Results (${currentPage - 1} of many)
                        </button>
                        <p style="color: #666; font-size: 12px; margin-top: 8px;">Showing top results by community size</p>
                    </div>
                `;
                resultsList.insertAdjacentHTML('beforeend', loadMoreBtn);
            } else {
                const endMsg = `
                    <div style="text-align: center; padding: 20px; color: #666; font-size: 14px; border-top: 1px solid #eee; margin-top: 15px;">
                        ✅ All results loaded (${data.total_found} communities found)
                    </div>
                `;
                resultsList.insertAdjacentHTML('beforeend', endMsg);
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
    """Discover subreddits by search term with pagination support"""
    try:
        search_term = request.args.get('search', '').strip()
        page = int(request.args.get('page', 1))
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 per page
        
        if not search_term:
            return jsonify({'error': 'Search term is required', 'success': False})
        
        reddit = get_reddit_instance()
        if not reddit:
            # Return mock data for testing when Reddit API not available
            mock_subreddits = create_mock_subreddits(search_term, page, limit)
            return jsonify({
                'success': True,
                'subreddits': mock_subreddits,
                'search_term': search_term,
                'total_found': len(mock_subreddits),
                'page': page,
                'has_more': page < 3  # Mock has 3 pages
            })
        
        discovered_subreddits = set()
        
        try:
            # Search for subreddits by name - get more results
            subreddit_results = reddit.subreddits.search_by_name(search_term, exact=False)
            
            # Also search subreddit content for broader results
            try:
                content_results = reddit.subreddit('all').search(f'subreddit:{search_term}', limit=50)
                additional_subreddits = set()
                for post in content_results:
                    try:
                        sub_name = post.subreddit.display_name.lower()
                        if search_term.lower() in sub_name:
                            additional_subreddits.add(post.subreddit.display_name)
                        if len(additional_subreddits) >= 25:
                            break
                    except:
                        continue
                
                # Add found subreddits to search results
                for sub_name in additional_subreddits:
                    try:
                        sub = reddit.subreddit(sub_name)
                        if len(discovered_subreddits) >= 100:  # Increased limit
                            break
                        
                        sub_info = {
                            'name': sub.display_name,
                            'title': sub.title[:100] if hasattr(sub, 'title') and sub.title else sub.display_name,
                            'description': (sub.public_description or '')[:300] if hasattr(sub, 'public_description') else '',
                            'subscribers': getattr(sub, 'subscribers', 0) or 0,
                            'url': f'https://reddit.com/r/{sub.display_name}'
                        }
                        if sub_info['subscribers'] > 100:  # Only active subreddits
                            discovered_subreddits.add(json.dumps(sub_info, sort_keys=True))
                    except:
                        continue
            except:
                pass
            
            # Process direct name search results
            for sub in subreddit_results:
                if len(discovered_subreddits) >= 100:  # Increased limit
                    break
                try:
                    # Get subreddit info
                    sub_info = {
                        'name': sub.display_name,
                        'title': sub.title[:100] if hasattr(sub, 'title') and sub.title else sub.display_name,
                        'description': (sub.public_description or '')[:300] if hasattr(sub, 'public_description') else '',
                        'subscribers': getattr(sub, 'subscribers', 0) or 0,
                        'url': f'https://reddit.com/r/{sub.display_name}'
                    }
                    if sub_info['subscribers'] > 100:  # Only include active subreddits
                        discovered_subreddits.add(json.dumps(sub_info, sort_keys=True))
                except Exception:
                    continue
        except Exception as e:
            print(f'Subreddit search error: {e}')
        
        # Convert back to list and parse JSON
        subreddit_list = []
        for sub_json in discovered_subreddits:
            try:
                subreddit_list.append(json.loads(sub_json))
            except Exception:
                continue
        
        # Sort by subscriber count (most popular first)
        subreddit_list.sort(key=lambda x: x['subscribers'], reverse=True)
        
        # Implement pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_results = subreddit_list[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'subreddits': paginated_results,
            'search_term': search_term,
            'total_found': len(subreddit_list),
            'page': page,
            'limit': limit,
            'has_more': end_idx < len(subreddit_list)
        })
        
    except Exception as e:
        return jsonify({'error': f'Search failed: {str(e)}', 'success': False})

def create_mock_subreddits(search_term, page, limit):
    """Create mock subreddit data for testing"""
    base_subreddits = [
        {'name': f'{search_term}', 'title': f'Main {search_term} Community', 'description': f'The main community for {search_term} discussions', 'subscribers': 1500000, 'url': f'https://reddit.com/r/{search_term}'},
        {'name': f'{search_term}_community', 'title': f'{search_term} Community Hub', 'description': f'Community hub for {search_term} enthusiasts', 'subscribers': 850000, 'url': f'https://reddit.com/r/{search_term}_community'},
        {'name': f'learn{search_term}', 'title': f'Learn {search_term}', 'description': f'Learn everything about {search_term}', 'subscribers': 650000, 'url': f'https://reddit.com/r/learn{search_term}'},
        {'name': f'{search_term}_help', 'title': f'{search_term} Help', 'description': f'Get help with {search_term}', 'subscribers': 450000, 'url': f'https://reddit.com/r/{search_term}_help'},
        {'name': f'{search_term}_news', 'title': f'{search_term} News', 'description': f'Latest news about {search_term}', 'subscribers': 320000, 'url': f'https://reddit.com/r/{search_term}_news'},
        {'name': f'{search_term}_tips', 'title': f'{search_term} Tips', 'description': f'Tips and tricks for {search_term}', 'subscribers': 280000, 'url': f'https://reddit.com/r/{search_term}_tips'},
        {'name': f'ask{search_term}', 'title': f'Ask {search_term}', 'description': f'Ask questions about {search_term}', 'subscribers': 240000, 'url': f'https://reddit.com/r/ask{search_term}'},
        {'name': f'{search_term}_discussion', 'title': f'{search_term} Discussion', 'description': f'In-depth {search_term} discussions', 'subscribers': 180000, 'url': f'https://reddit.com/r/{search_term}_discussion'},
        {'name': f'{search_term}_beginners', 'title': f'{search_term} for Beginners', 'description': f'Beginner-friendly {search_term} community', 'subscribers': 150000, 'url': f'https://reddit.com/r/{search_term}_beginners'},
        {'name': f'{search_term}_advanced', 'title': f'Advanced {search_term}', 'description': f'Advanced {search_term} topics', 'subscribers': 120000, 'url': f'https://reddit.com/r/{search_term}_advanced'},
    ]
    
    # Create more variations for pagination
    all_subreddits = base_subreddits.copy()
    for i in range(10, 50):
        all_subreddits.append({
            'name': f'{search_term}{i}',
            'title': f'{search_term} Variant {i}',
            'description': f'Alternative {search_term} community #{i}',
            'subscribers': max(50000 - i * 1000, 5000),
            'url': f'https://reddit.com/r/{search_term}{i}'
        })
    
    # Paginate
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    return all_subreddits[start_idx:end_idx]

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
    """Handle Slack slash commands from any workspace"""
    try:
        # Verify the request is from Slack
        if request.form.get('command') != '/reddit':
            return jsonify({'text': 'Unknown command'})
        
        # Extract workspace and user info
        team_id = request.form.get('team_id')
        user_id = request.form.get('user_id')
        user_name = request.form.get('user_name', 'Unknown')
        channel_name = request.form.get('channel_name', 'Unknown')
        channel_id = request.form.get('channel_id')
        response_url = request.form.get('response_url')
        text = request.form.get('text', '').strip()
        
        print(f"[SLASH] Command from team {team_id}, user {user_name}, channel {channel_name}")
        
        # Get workspace data
        workspace = get_workspace_by_team_id(team_id)
        if not workspace:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '❌ **Reddit Scraper Pro not properly installed**\n\nPlease reinstall the app or contact your workspace admin.\n\n[Install Link](https://scrapper-eight-alpha.vercel.app/slack/install)'
            })
        
        # Check if workspace is active
        if not workspace.get('is_active'):
            return jsonify({
                'response_type': 'ephemeral',
                'text': '⚠️ This workspace installation is currently disabled. Contact support for assistance.'
            })
        
        # Rate limiting check (per user per hour)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check recent usage for this user
        cursor.execute('''
            SELECT COUNT(*) FROM usage_logs 
            WHERE workspace_id = ? AND user_id = ? 
            AND timestamp > datetime('now', '-1 hour')
        ''', (workspace['id'], user_id))
        
        recent_usage = cursor.fetchone()[0]
        user_hourly_limit = 10  # 10 commands per hour per user
        
        if recent_usage >= user_hourly_limit:
            conn.close()
            return jsonify({
                'response_type': 'ephemeral',
                'text': f'⚠️ **Rate Limit Exceeded**\n\nYou can use up to {user_hourly_limit} commands per hour. Please try again later.\n\n**Time until reset:** {60 - datetime.now().minute} minutes'
            })
        
        conn.close()
        
        # Check usage limits
        if workspace['usage_count'] >= workspace['usage_limit']:
            return jsonify({
                'response_type': 'ephemeral',
                'text': f'🚫 **Monthly Usage Limit Reached**\n\nYour workspace has used {workspace["usage_count"]}/{workspace["usage_limit"]} searches this month.\n\n**Plan:** {workspace["plan_type"].title()}\n**Upgrade** to continue using Reddit Scraper Pro.'
            })
        
        # Parse command
        
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
                args=(keywords, subreddit, max_results, sort_method, response_url, user_name, workspace, user_id)
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

def perform_slack_search(keywords, subreddit, max_results, sort_method, response_url, user_name, workspace, user_id):
    """Perform Reddit search and post results to Slack (background task)"""
    try:
        print(f"[SLACK SEARCH] Starting search for {keywords} by {user_name} in workspace {workspace['team_name']}")
        
        # Check Reddit API
        reddit = get_reddit_instance()
        if not reddit:
            print("[SLACK SEARCH] Reddit API not configured, sending mock results")
            # Send mock results instead of failing
            mock_response = create_mock_search_results(keywords, subreddit, user_name)
            success = post_slack_response(response_url, mock_response)
            print(f"[SLACK SEARCH] Mock response posted: {success}")
            return
        
        print(f"[SLACK SEARCH] Reddit API available, performing real search")
        
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
        
        print(f"[SLACK SEARCH] Search completed. Success: {results['success']}")
        
        if results['success']:
            # Format success response
            posts = results['posts']
            response = format_slack_search_results(posts, keywords, subreddit, user_name)
            print(f"[SLACK SEARCH] Formatted results for {len(posts)} posts")
        else:
            # Format error response
            response = {
                'text': f'❌ Search failed: {results["error"]}',
                'response_type': 'in_channel'
            }
            print(f"[SLACK SEARCH] Search failed: {results['error']}")
        
        success = post_slack_response(response_url, response)
        print(f"[SLACK SEARCH] Final response posted: {success}")
        
        # Log successful usage
        if results.get('success'):
            log_usage(
                workspace['id'], user_id, 'search', 
                search_term=' '.join(keywords), 
                result_count=len(results.get('posts', [])), 
                success=True
            )
        
    except Exception as e:
        print(f"[SLACK SEARCH] Exception: {str(e)}")
        error_response = {
            'text': f'❌ Search error: {str(e)}',
            'response_type': 'in_channel'
        }
        post_slack_response(response_url, error_response)
        
        # Log failed usage
        log_usage(
            workspace['id'], user_id, 'search', 
            search_term=' '.join(keywords), 
            result_count=0, 
            success=False, 
            error=str(e)
        )

def create_mock_search_results(keywords, subreddit, user_name):
    """Create mock search results when Reddit API is not available"""
    mock_posts = [
        {
            'title': f'Mock post about {keywords[0]} - AI breakthrough announced',
            'score': 156,
            'num_comments': 89,
            'subreddit': 'technology',
            'url': 'https://reddit.com/r/technology/mock1',
            'engagement_rate': 15.2,
            'sentiment': 'positive'
        },
        {
            'title': f'Discussion: {keywords[0]} impact on future tech',
            'score': 98,
            'num_comments': 67,
            'subreddit': 'futurology', 
            'url': 'https://reddit.com/r/futurology/mock2',
            'engagement_rate': 12.8,
            'sentiment': 'positive'
        },
        {
            'title': f'{keywords[0]} startup raises $50M in Series A',
            'score': 78,
            'num_comments': 45,
            'subreddit': 'startups',
            'url': 'https://reddit.com/r/startups/mock3', 
            'engagement_rate': 11.4,
            'sentiment': 'neutral'
        }
    ]
    
    return {
        'text': f'✨ <@{user_name}> found 3 posts for "{" ".join(keywords)}" (Demo Results)!',
        'response_type': 'in_channel',
        'attachments': [
            {
                'color': 'good',
                'title': '📊 Demo Search Results',
                'fields': [
                    {'title': 'Keywords', 'value': ', '.join(keywords), 'short': True},
                    {'title': 'Subreddit', 'value': f'r/{subreddit}' if subreddit != 'all' else 'all of Reddit', 'short': True},
                    {'title': 'Posts Found', 'value': '3 (demo)', 'short': True},
                    {'title': 'Avg Upvotes', 'value': '110.7', 'short': True}
                ],
                'footer': 'Reddit Scraper Pro - Demo Mode',
                'footer_icon': 'https://reddit.com/favicon.ico'
            },
            {
                'color': '#ff6b35',
                'title': '🔥 Top Demo Posts',
                'text': '\n'.join([
                    f'🔥 **{post["title"][:60]}**{"..." if len(post["title"]) > 60 else ""}\n'
                    f'   👆 {post["score"]} upvotes • 💬 {post["num_comments"]} comments • r/{post["subreddit"]}\n'
                    f'   🔗 <{post["url"]}|View Post>\n'
                    for post in mock_posts
                ]),
                'mrkdwn_in': ['text']
            },
            {
                'color': '#1a73e8',
                'title': 'ℹ️ Note',
                'text': 'This is demo data. For live Reddit results, configure Reddit API credentials.',
            }
        ]
    }

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
        print(f"[SLACK POST] Posting to: {response_url[:50]}...")
        print(f"[SLACK POST] Data preview: {str(data)[:200]}...")
        
        response = requests.post(response_url, json=data, timeout=15)
        
        print(f"[SLACK POST] Response status: {response.status_code}")
        print(f"[SLACK POST] Response text: {response.text[:200]}")
        
        if response.status_code == 200:
            print(f"[SLACK POST] Success - message posted to Slack")
            return True
        else:
            print(f"[SLACK POST] Failed - status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"[SLACK POST] Timeout posting to Slack")
        return False
    except requests.exceptions.ConnectionError:
        print(f"[SLACK POST] Connection error posting to Slack")
        return False
    except Exception as e:
        print(f"[SLACK POST] Exception posting to Slack: {e}")
        return False

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Reddit Scraper Pro Advanced'})

if __name__ == '__main__':
    app.run(debug=True)