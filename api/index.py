"""
WSGI Entry Point for Vercel Serverless Deployment
Reddit Scraper Pro - Universal Multi-Tenant Slack App
"""

import sys
import os

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set default environment variables for production BEFORE importing app
if not os.getenv('SECRET_KEY'):
    os.environ['SECRET_KEY'] = 'production-secret-key-change-this-immediately'
if not os.getenv('ADMIN_KEY'):
    os.environ['ADMIN_KEY'] = 'production-admin-key-change-this-immediately'
if not os.getenv('VERCEL'):
    os.environ['VERCEL'] = '1'  # Signal that we're on Vercel

try:
    # Import the Flask app
    from advanced_app import app
    
    # Initialize database on import
    from advanced_app import init_database
    init_database()
    
except Exception as e:
    print(f"Error importing app: {e}")
    # Create a minimal Flask app for error handling
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error_page():
        return f'Application Error: {str(e)}', 500

# For WSGI compatibility
application = app

if __name__ == '__main__':
    app.run(debug=False)
