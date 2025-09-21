#!/usr/bin/env python3
"""Demo script showing how Reddit Scraper Pro Universal Slack App works"""

import os
import threading
import time
import webbrowser
from advanced_app import app, init_database, PRICING_PLANS

# Set environment variables for demo
os.environ['SECRET_KEY'] = 'demo-encryption-key-not-for-production'
os.environ['ADMIN_KEY'] = 'demo-admin-key'
os.environ['SLACK_CLIENT_ID'] = 'demo-client-id'
os.environ['SLACK_CLIENT_SECRET'] = 'demo-client-secret'

def print_demo_info():
    """Print demo information"""
    print("=" * 80)
    print("🎉 REDDIT SCRAPER PRO - UNIVERSAL SLACK APP DEMO")
    print("=" * 80)
    print()
    print("📊 PRICING PLANS:")
    for plan, details in PRICING_PLANS.items():
        print(f"  • {plan.upper():12} - {details['searches_per_month']:5,} searches/month - ${details['price']:2}")
    print()
    print("🌐 DEMO ENDPOINTS:")
    print("  • http://localhost:5001/              - Home page")  
    print("  • http://localhost:5001/slack/install - Installation page")
    print("  • http://localhost:5001/pricing       - Pricing page")
    print("  • http://localhost:5001/admin/workspaces?key=demo-admin-key - Admin dashboard")
    print("  • http://localhost:5001/admin/billing?key=demo-admin-key   - Billing dashboard")
    print()
    print("🔧 HOW IT WORKS:")
    print("1. Any Slack workspace visits /slack/install")
    print("2. OAuth 2.0 flow captures their team tokens securely")  
    print("3. Tokens are encrypted and stored in database")
    print("4. Users can use /reddit commands in their Slack")
    print("5. Admin can monitor all workspaces via dashboard")
    print("6. Usage tracking and billing automatically managed")
    print()
    print("🚀 Starting demo server on http://localhost:5001")
    print("   Press Ctrl+C to stop")
    print("=" * 80)

def open_demo_pages():
    """Open demo pages in browser after delay"""
    time.sleep(2)
    pages = [
        'http://localhost:5001/',
        'http://localhost:5001/pricing',
        'http://localhost:5001/admin/workspaces?key=demo-admin-key'
    ]
    
    for page in pages:
        try:
            webbrowser.open(page)
            time.sleep(1)
        except:
            pass

if __name__ == "__main__":
    # Initialize database
    init_database()
    
    # Print demo info
    print_demo_info()
    
    # Start browser opening in background
    browser_thread = threading.Thread(target=open_demo_pages)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start Flask app
    try:
        app.run(host='0.0.0.0', port=5001, debug=True)
    except KeyboardInterrupt:
        print("\n\n✅ Demo stopped. Thanks for trying Reddit Scraper Pro!")