#!/usr/bin/env python3
"""
Package Reddit Scraper for Delivery
Creates a clean, ready-to-deliver package
"""

import os
import shutil
import zipfile
from datetime import datetime

def create_delivery_package():
    """Create a clean delivery package."""
    
    # Package info
    package_name = "reddit-scraper-v1.0"
    timestamp = datetime.now().strftime("%Y%m%d")
    
    print("📦 Creating Reddit Scraper Delivery Package...")
    print(f"Package: {package_name}")
    
    # Create package directory
    package_dir = f"../{package_name}"
    if os.path.exists(package_dir):
        shutil.rmtree(package_dir)
    
    os.makedirs(package_dir)
    
    # Files to include
    files_to_copy = [
        # Main scripts
        "reddit_scraper.py",
        "run_scraper.py",
        "install.py",
        "setup.py",
        "setup_credentials.py",
        
        # Configuration
        "requirements.txt",
        ".env.template",
        ".env",
        
        # Documentation
        "README.md",
        "QUICK_START.md",
        
        # Config directory
        "config/",
    ]
    
    # Copy files
    for file_path in files_to_copy:
        src = file_path
        dst = os.path.join(package_dir, file_path)
        
        if os.path.isdir(src):
            shutil.copytree(src, dst)
            print(f"✓ Copied directory: {file_path}")
        elif os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            print(f"✓ Copied file: {file_path}")
        else:
            print(f"⚠ Missing: {file_path}")
    
    # Create empty output directory
    os.makedirs(os.path.join(package_dir, "output"), exist_ok=True)
    
    # Create a sample output file to show structure
    with open(os.path.join(package_dir, "output", "README.txt"), "w") as f:
        f.write("Excel files from Reddit scraping will be saved here.\n")
        f.write("Files will be automatically named with timestamps.\n")
    
    print("✓ Created output directory")
    
    # Create ZIP file
    zip_filename = f"{package_name}-{timestamp}.zip"
    zip_path = f"../{zip_filename}"
    
    print(f"\n📁 Creating ZIP archive: {zip_filename}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, package_dir)
                zipf.write(file_path, arc_name)
                print(f"  + {arc_name}")
    
    # Get file size
    zip_size = os.path.getsize(zip_path) / 1024  # KB
    
    print(f"\n✅ Package created successfully!")
    print(f"📦 Package directory: {os.path.abspath(package_dir)}")
    print(f"📁 ZIP file: {os.path.abspath(zip_path)} ({zip_size:.1f} KB)")
    
    return package_dir, zip_path

def print_delivery_instructions(package_dir, zip_path):
    """Print delivery instructions."""
    
    print("\n" + "=" * 70)
    print("🚚 DELIVERY INSTRUCTIONS")
    print("=" * 70)
    print("\n📋 What to deliver:")
    print(f"   • ZIP file: {os.path.basename(zip_path)}")
    print(f"   • Or folder: {os.path.basename(package_dir)}")
    
    print("\n📝 Instructions for the recipient:")
    print("   1. Extract the ZIP file")
    print("   2. Open terminal/command prompt in the extracted folder")
    print("   3. Run: python3 install.py")
    print("   4. Follow the setup prompts")
    print("   5. Start scraping with: python3 run_scraper.py")
    
    print("\n🎯 Key Features to mention:")
    print("   • Searches ALL of Reddit or specific subreddits")
    print("   • Exports to professional Excel files")
    print("   • Up to 25 pages (2,500 posts) per search")
    print("   • Collects titles, URLs, scores, comments, dates")
    print("   • Easy interactive mode + advanced command line")
    print("   • Built-in rate limiting and error handling")
    
    print("\n📚 Documentation included:")
    print("   • QUICK_START.md - 5-minute setup guide")
    print("   • README.md - Complete documentation")
    print("   • install.py - One-click installer")
    
    print("\n💡 Requirements:")
    print("   • Python 3.7+")
    print("   • Internet connection")
    print("   • Free Reddit account (for API access)")
    
    print("\n" + "=" * 70)
    print("✅ Ready for delivery!")
    print("=" * 70)

def main():
    """Main function."""
    print("🚀 Reddit Scraper - Package for Delivery")
    print("=" * 50)
    
    try:
        package_dir, zip_path = create_delivery_package()
        print_delivery_instructions(package_dir, zip_path)
        
        # Ask if they want to open the package location
        open_folder = input("\nOpen package location? (y/n): ").strip().lower()
        if open_folder in ['y', 'yes']:
            os.system(f"open {os.path.dirname(os.path.abspath(zip_path))}")
            
    except Exception as e:
        print(f"❌ Error creating package: {e}")

if __name__ == "__main__":
    main()