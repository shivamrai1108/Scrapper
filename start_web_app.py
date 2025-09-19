#!/usr/bin/env python3
"""
Reddit Scraper Web App Launcher
Easy launcher for the Reddit Scraper web interface
"""

import os
import sys
import subprocess
import platform

def check_streamlit_installation():
    """Check if Streamlit is installed"""
    try:
        import streamlit
        return True
    except ImportError:
        return False

def install_requirements():
    """Install required packages"""
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ All packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing packages: {e}")
        return False

def check_reddit_credentials():
    """Check if Reddit API credentials exist"""
    from dotenv import load_dotenv
    load_dotenv()
    
    client_id = os.getenv('REDDIT_CLIENT_ID')
    client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    user_agent = os.getenv('REDDIT_USER_AGENT')
    
    return all([client_id, client_secret, user_agent])

def create_sample_env():
    """Create a sample .env file if it doesn't exist"""
    env_file = ".env"
    if not os.path.exists(env_file):
        sample_content = """# Reddit API Credentials
# Get these from: https://www.reddit.com/prefs/apps/
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=RedditScraper/1.0 by YourUsername

# Optional: For authenticated requests (higher rate limits)
# REDDIT_USERNAME=your_reddit_username
# REDDIT_PASSWORD=your_reddit_password
"""
        with open(env_file, 'w') as f:
            f.write(sample_content)
        print(f"📝 Created sample {env_file} file. Please add your Reddit API credentials.")
        return False
    return True

def launch_web_app():
    """Launch the Streamlit web application"""
    print("\n🚀 Starting Reddit Scraper Web Interface...")
    print("🌐 The app will open in your default web browser")
    print("📱 Access it at: http://localhost:8501")
    print("⏹️  Press Ctrl+C to stop the server\n")
    
    try:
        # Change to the script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "web_frontend.py",
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Reddit Scraper Web App stopped.")
    except Exception as e:
        print(f"❌ Error launching web app: {e}")

def main():
    """Main launcher function"""
    print("🔍 Reddit Scraper Web Interface Launcher")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher required!")
        return
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check and install Streamlit if needed
    if not check_streamlit_installation():
        print("📦 Streamlit not found. Installing required packages...")
        if not install_requirements():
            print("❌ Failed to install required packages. Please install manually:")
            print("   pip install -r requirements.txt")
            return
    else:
        print("✅ Streamlit found")
    
    # Check Reddit credentials
    if not create_sample_env():
        print("\n🔧 Setup Required:")
        print("1. Edit the .env file with your Reddit API credentials")
        print("2. Get credentials from: https://www.reddit.com/prefs/apps/")
        print("3. Run this script again")
        return
    
    if not check_reddit_credentials():
        print("⚠️  Reddit API credentials not configured!")
        print("📝 Please edit the .env file with your Reddit API credentials")
        print("🔗 Get them from: https://www.reddit.com/prefs/apps/")
        
        choice = input("🤔 Continue anyway? (y/n): ").strip().lower()
        if choice not in ['y', 'yes']:
            return
    else:
        print("✅ Reddit API credentials found")
    
    # Launch the web app
    launch_web_app()

if __name__ == "__main__":
    main()