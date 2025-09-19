# Reddit Scraper - Quick Start Guide

🚀 **Get started scraping Reddit in 5 minutes!**

## What This Tool Does

- 🔍 Searches Reddit for your keywords across **ALL of Reddit or specific subreddits**
- 📊 Exports results to **formatted Excel files** 
- 🎯 Finds up to **25 pages (2,500 posts)** per search
- 📈 Collects **post titles, links, scores, comments, dates, and more**
- ⚡ **Fast and reliable** with built-in rate limiting

## Super Quick Setup (2 minutes)

### 1. Install Python Dependencies
```bash
python3 setup.py
```

### 2. Get Reddit API Access
1. Go to: https://www.reddit.com/prefs/apps
2. Click "Create App" → Choose "script"
3. Fill any name, use `http://localhost:8080` as redirect URI
4. Copy your **Client ID** and **Client Secret**

### 3. Add Your Credentials
```bash
python3 setup_credentials.py
```
Enter your Client ID, Secret, and Reddit username when prompted.

## Usage

### Easy Mode (Interactive)
```bash
python3 run_scraper.py
```
Just follow the prompts!

### Command Line (Advanced)
```bash
# Basic search
python3 reddit_scraper.py "your keyword"

# Multiple keywords
python3 reddit_scraper.py "AI" "machine learning" "deep learning"

# Specific subreddit
python3 reddit_scraper.py "cryptocurrency" --subreddit CryptoCurrency

# Limit results
python3 reddit_scraper.py "python" --max-results 500

# Sort by top posts this week
python3 reddit_scraper.py "gaming" --sort top --time-filter week
```

## Output

✅ Excel files saved in the `output/` folder  
✅ Contains: Title, URL, Score, Comments, Date, Subreddit, Keywords Found  
✅ Includes summary sheet with statistics  

## Example Results

- **25 pages** of results (up to 2,500 posts)
- **Rich data**: Post titles, direct URLs, scores, comment counts
- **Smart filtering**: Only posts containing your keywords
- **Professional formatting**: Ready-to-use Excel files

---

**Need help?** Check the full `README.md` for detailed instructions!