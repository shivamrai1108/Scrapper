#!/usr/bin/env python3
"""
Setup script for Reddit Scraper
"""

import os
import sys
import subprocess
import shutil

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required.")
        print(f"Current version: {sys.version}")
        return False
    print(f"✓ Python {sys.version.split()[0]} detected")
    return True

def install_requirements():
    """Install required packages."""
    print("\n📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ All packages installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install packages: {e}")
        return False

def setup_env_file():
    """Setup environment file."""
    print("\n🔧 Setting up environment file...")
    
    if os.path.exists(".env"):
        print("✓ .env file already exists")
        return True
    
    if os.path.exists(".env.template"):
        try:
            shutil.copy(".env.template", ".env")
            print("✓ Created .env file from template")
            print("⚠️  Please edit .env file with your Reddit API credentials")
            return True
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
            return False
    else:
        print("❌ .env.template file not found")
        return False

def create_output_directory():
    """Create output directory."""
    print("\n📁 Creating output directory...")
    try:
        os.makedirs("output", exist_ok=True)
        print("✓ Output directory created")
        return True
    except Exception as e:
        print(f"❌ Failed to create output directory: {e}")
        return False

def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETED!")
    print("="*60)
    print("\n📋 NEXT STEPS:")
    print("1. Edit the .env file with your Reddit API credentials:")
    print("   - Go to https://www.reddit.com/prefs/apps")
    print("   - Create a new 'script' app")
    print("   - Add your credentials to .env file")
    print("\n2. Test the installation:")
    print("   python run_scraper.py")
    print("\n3. For command line usage:")
    print('   python reddit_scraper.py "your keyword"')
    print("\n📖 Check README.md for detailed instructions")
    print("="*60)

def main():
    """Main setup function."""
    print("="*60)
    print("REDDIT SCRAPER SETUP")
    print("="*60)
    
    success = True
    
    # Check Python version
    if not check_python_version():
        success = False
    
    # Install requirements
    if success and not install_requirements():
        success = False
    
    # Setup environment file
    if success and not setup_env_file():
        success = False
    
    # Create output directory
    if success and not create_output_directory():
        success = False
    
    if success:
        print_next_steps()
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()