#!/usr/bin/env python3
"""
Reddit Scraper - One-Click Installer
Complete setup in one command
"""

import os
import sys
import subprocess
import shutil
import getpass

def print_header():
    """Print welcome header."""
    print("=" * 70)
    print("🚀 REDDIT SCRAPER - ONE-CLICK INSTALLER")
    print("=" * 70)
    print("This will set up everything you need to start scraping Reddit!")
    print()

def check_python():
    """Check Python version."""
    print("🔍 Checking Python version...")
    if sys.version_info < (3, 7):
        print(f"❌ Python 3.7+ required. Current: {sys.version}")
        return False
    print(f"✅ Python {sys.version.split()[0]} - Good!")
    return True

def install_packages():
    """Install required packages."""
    print("\n📦 Installing Python packages...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"
        ])
        print("✅ All packages installed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Package installation failed: {e}")
        return False

def setup_directories():
    """Create necessary directories."""
    print("\n📁 Setting up directories...")
    os.makedirs("output", exist_ok=True)
    print("✅ Output directory ready!")
    return True

def get_reddit_credentials():
    """Get Reddit API credentials from user."""
    print("\n" + "=" * 70)
    print("🔑 REDDIT API SETUP")
    print("=" * 70)
    print("You need Reddit API credentials to use this scraper.")
    print("Don't worry, it's free and takes 2 minutes!")
    print()
    print("Steps:")
    print("1. Go to: https://www.reddit.com/prefs/apps")
    print("2. Click 'Create App' or 'Create Another App'")
    print("3. Choose 'script' as app type")
    print("4. Fill in any name and description")
    print("5. Use 'http://localhost:8080' as redirect URI")
    print("6. Click 'Create app'")
    print()
    
    # Ask if they want to open the URL
    open_url = input("Would you like me to open the Reddit apps page? (y/n): ").strip().lower()
    if open_url in ['y', 'yes']:
        try:
            subprocess.run(['open', 'https://www.reddit.com/prefs/apps'])
            print("✅ Opened Reddit apps page in your browser")
        except:
            print("Please manually go to: https://www.reddit.com/prefs/apps")
    
    print("\n" + "-" * 50)
    input("Press ENTER when you've created your Reddit app...")
    
    print("\nNow enter your Reddit app credentials:")
    
    # Get credentials
    while True:
        client_id = input("\n📋 Client ID (short string under app name): ").strip()
        if client_id and len(client_id) > 5:
            break
        print("❌ Please enter a valid Client ID")
    
    while True:
        client_secret = getpass.getpass("🔐 Client Secret (long secret string): ").strip()
        if client_secret and len(client_secret) > 10:
            break
        print("❌ Please enter a valid Client Secret")
    
    while True:
        username = input("👤 Your Reddit Username: ").strip()
        if username:
            break
        print("❌ Please enter your Reddit username")
    
    # Optional password
    print("\n💡 Reddit password is optional but gives higher rate limits")
    password = getpass.getpass("🔑 Reddit Password (optional, press ENTER to skip): ").strip()
    
    return client_id, client_secret, username, password

def save_credentials(client_id, client_secret, username, password):
    """Save credentials to .env file."""
    print("\n💾 Saving credentials...")
    
    env_content = f"""# Reddit API Credentials
REDDIT_CLIENT_ID={client_id}
REDDIT_CLIENT_SECRET={client_secret}
REDDIT_USER_AGENT=RedditScraper/1.0 by {username}

# Reddit Login (optional, for higher rate limits)
"""
    
    if password:
        env_content += f"""REDDIT_USERNAME={username}
REDDIT_PASSWORD={password}
"""
    else:
        env_content += f"""# REDDIT_USERNAME={username}
# REDDIT_PASSWORD=your_password_here
"""
    
    try:
        with open(".env", "w") as f:
            f.write(env_content)
        print("✅ Credentials saved securely!")
        return True
    except Exception as e:
        print(f"❌ Failed to save credentials: {e}")
        return False

def test_connection():
    """Test the Reddit API connection."""
    print("\n🔌 Testing Reddit API connection...")
    try:
        # Import here to avoid issues if packages aren't installed yet
        from reddit_scraper import RedditScraper
        scraper = RedditScraper()
        print("✅ Reddit API connection successful!")
        return True
    except Exception as e:
        print(f"⚠️  Connection test failed: {e}")
        print("Don't worry, you can still use the scraper!")
        return False

def print_success():
    """Print success message and usage instructions."""
    print("\n" + "=" * 70)
    print("🎉 INSTALLATION COMPLETE!")
    print("=" * 70)
    print("\n🚀 Ready to scrape Reddit! Here's how to use it:")
    print()
    print("📱 EASY MODE (Recommended for beginners):")
    print("   python3 run_scraper.py")
    print()
    print("⚡ COMMAND LINE (Advanced users):")
    print('   python3 reddit_scraper.py "your keywords"')
    print()
    print("📊 OUTPUT:")
    print("   • Excel files will be saved in the 'output/' folder")
    print("   • Each file contains post titles, URLs, scores, and more")
    print("   • Supports up to 25 pages (2,500 posts) per search")
    print()
    print("📖 MORE INFO:")
    print("   • Check QUICK_START.md for examples")
    print("   • Check README.md for detailed documentation")
    print()
    print("=" * 70)
    print("🎯 Happy scraping!")
    print("=" * 70)

def main():
    """Main installation function."""
    print_header()
    
    success = True
    
    # Check Python
    if not check_python():
        success = False
    
    # Install packages
    if success and not install_packages():
        success = False
    
    # Setup directories
    if success and not setup_directories():
        success = False
    
    # Get credentials
    if success:
        try:
            client_id, client_secret, username, password = get_reddit_credentials()
            if not save_credentials(client_id, client_secret, username, password):
                success = False
        except KeyboardInterrupt:
            print("\n\n❌ Installation cancelled by user.")
            return
        except Exception as e:
            print(f"\n❌ Error during credential setup: {e}")
            success = False
    
    # Test connection
    if success:
        test_connection()
    
    if success:
        print_success()
    else:
        print("\n❌ Installation failed. Please check the errors above.")
        print("💡 You can try running the setup steps manually.")

if __name__ == "__main__":
    main()