"""
WSGI Entry Point for Vercel Serverless Deployment
Reddit Scraper Pro - Universal Multi-Tenant Slack App
"""

import sys
import os

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app
from advanced_app import app

# Set default environment variables for production
if not os.getenv('SECRET_KEY'):
    os.environ['SECRET_KEY'] = 'production-secret-key-change-this'
if not os.getenv('ADMIN_KEY'):
    os.environ['ADMIN_KEY'] = 'production-admin-key-change-this'

# This is the entry point for Vercel
def handler(event, context):
    """Serverless function handler for Vercel"""
    return app(event, context)

# For WSGI compatibility
application = app

if __name__ == '__main__':
    app.run(debug=False)