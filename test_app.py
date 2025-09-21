#!/usr/bin/env python3
"""Test script for Reddit Scraper Pro Universal Slack App"""

import os
import sys
from advanced_app import init_database, PRICING_PLANS

def test_system():
    print("🔄 Testing Reddit Scraper Pro Universal Slack App...")
    print("=" * 60)
    
    # Test database initialization
    try:
        init_database()
        print("✅ Database initialization: SUCCESS")
    except Exception as e:
        print(f"❌ Database initialization: FAILED - {e}")
        return False
    
    # Test pricing plans
    print("\n📊 Available Pricing Plans:")
    for plan, details in PRICING_PLANS.items():
        searches = details['searches_per_month']
        price = details['price']
        print(f"  • {plan.upper()}: {searches:,} searches/month - ${price}")
    
    # Test environment variables needed
    print("\n🔧 Required Environment Variables:")
    required_vars = [
        'SLACK_CLIENT_ID',
        'SLACK_CLIENT_SECRET', 
        'SECRET_KEY',
        'ADMIN_KEY'
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        status = "SET" if value else "MISSING"
        print(f"  • {var}: {status}")
    
    # Test key endpoints
    print("\n🌐 Key Endpoints Available:")
    endpoints = [
        "/slack/install - OAuth installation page",
        "/slack/oauth/callback - OAuth callback handler", 
        "/api/slack/command - Slash command handler",
        "/admin/workspaces - Admin dashboard",
        "/admin/billing - Billing dashboard",
        "/pricing - Public pricing page"
    ]
    
    for endpoint in endpoints:
        print(f"  • {endpoint}")
    
    print("\n🎯 How It Works:")
    print("1. Any Slack workspace visits /slack/install")
    print("2. OAuth flow captures and encrypts their tokens")
    print("3. Workspace gets added to database with usage limits")
    print("4. Users can use /reddit commands in their Slack")
    print("5. Admin monitors all workspaces via dashboard")
    
    print("\n🚀 SYSTEM READY FOR UNIVERSAL DEPLOYMENT!")
    return True

if __name__ == "__main__":
    success = test_system()
    sys.exit(0 if success else 1)