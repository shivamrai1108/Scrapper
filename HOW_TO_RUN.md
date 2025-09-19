# 🔍 Reddit Scraper - How to Run

## 🚀 Super Quick Start (2 Steps!)

### **Step 1: Run the Launcher**
```bash
python3 start_web_app.py
```

### **Step 2: Use the Web Interface**
- Your browser will open automatically at `http://localhost:8501`
- Enter keywords in the sidebar
- Click "🚀 Start Search"
- Download your Excel results!

**That's it! The launcher handles everything else automatically.**

---

## 📋 Prerequisites

### **System Requirements:**
- ✅ **macOS, Windows, or Linux**
- ✅ **Python 3.7 or higher**
- ✅ **Internet connection**
- ✅ **Web browser**

### **Check Your Python Version:**
```bash
python3 --version
```
*Should show Python 3.7+ (like "Python 3.9.6")*

---

## 🔑 Reddit API Setup (One-Time, 5 Minutes)

### **Get Free Reddit API Credentials:**

1. **Go to:** https://www.reddit.com/prefs/apps/
2. **Click:** "Create App" or "Create Another App"
3. **Fill the form:**
   - **Name:** `Reddit Scraper` (any name)
   - **App type:** Select **"script"**
   - **Description:** `Personal data scraper`
   - **Redirect URI:** `http://localhost:8080`
4. **Click:** "Create app"
5. **Copy your credentials:**
   - **Client ID:** Short string under the app name
   - **Client Secret:** Longer secret string

### **Configure Credentials:**
When you first run the launcher, it will create a `.env` file. Edit it with your credentials:

```env
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=RedditScraper/1.0 by YourUsername
```

**Save the file and run the launcher again.**

---

## 🎮 How to Use

### **Web Interface (Recommended):**
1. Run: `python3 start_web_app.py`
2. Browser opens at `http://localhost:8501`
3. **Enter keywords** (one per line):
   ```
   iPhone
   Samsung
   Google Pixel
   ```
4. **Set options:**
   - Max Results: 50-500 (start small)
   - Sort: "relevance" for best results
   - Advanced filters if needed
5. **Click "🚀 Start Search"**
6. **Watch progress** in real-time
7. **Download Excel** when complete

### **Command Line (Advanced):**
```bash
# Basic search
python3 reddit_scraper.py "iPhone" "Samsung" --max-results 50

# Advanced search
python3 reddit_scraper.py "AI" "ChatGPT" --sort hot --days 7 --min-score 10
```

---

## 📊 What You Get

### **Excel Output Contains:**
- **50+ Data Columns** - Title, community, author, scores, dates
- **Sentiment Analysis** - Positive/negative/neutral classification
- **Engagement Metrics** - Virality scores, trending potential
- **Content Quality** - Spam detection, readability scores
- **Summary Statistics** - Overview of your search results

### **Web Interface Shows:**
- 📊 **Interactive Charts** - Sentiment distribution, engagement trends
- 🔥 **Top Posts** - Most engaging content found
- 📈 **Community Analysis** - Which subreddits are most active
- 📋 **Live Preview** - See results before downloading

---

## 🎯 Usage Examples

### **Brand Monitoring:**
```
Keywords: iPhone, Samsung Galaxy, Google Pixel
Sort: hot
Days Back: 7
Min Score: 5
```

### **Market Research:**
```
Keywords: electric car, Tesla, EV
Sort: relevance  
Max Results: 100
Sentiment: all
```

### **Tech Trends:**
```
Keywords: AI, ChatGPT, machine learning
Sort: new
Days Back: 3
Min Engagement: 2.0
```

---

## 🆘 Troubleshooting

### **"Python not found"**
```bash
# Try these commands:
python --version
python3 --version
py --version

# Install Python if needed from: https://python.org
```

### **"Reddit API credentials not found"**
- Make sure you created the Reddit app at https://www.reddit.com/prefs/apps/
- Check your `.env` file has the correct credentials
- Ensure no extra spaces in the credential values

### **"No results found"**
- Try broader keywords (e.g., "AI" instead of "artificial intelligence GPT-4")
- Remove time filters (set Days Back to 0)
- Try different sort methods: hot, new, top
- Check if the subreddit exists and is active

### **Web app won't start**
- Make sure port 8501 isn't used by another app
- Try: `streamlit run web_frontend.py --server.port 8502`
- Close other applications and try again

---

## 🔧 Manual Installation (If Needed)

If the launcher doesn't work, install manually:

```bash
# 1. Install required packages
pip3 install -r requirements.txt

# 2. Set up credentials (see above)

# 3. Run the web app
streamlit run web_frontend.py
```

---

## 💡 Pro Tips

### **For Best Results:**
- ✅ **Start small** - Try 50 results first, then scale up
- ✅ **Use "relevance" sort** for targeted searches
- ✅ **Try "hot" sort** for trending content
- ✅ **Set time filters** for recent discussions (7-30 days)
- ✅ **Use exact keywords** - "iPhone 15" not just "iPhone"

### **Performance:**
- 🚀 **Relevance searches** are fastest (uses Reddit API)
- 🐌 **Hot/new/top searches** are slower but more comprehensive
- ⚡ **Specific subreddits** search faster than "all"
- 📊 **Smaller result sets** process quicker

---

## 🎉 Ready to Start?

### **Just run this command:**
```bash
python3 start_web_app.py
```

### **Then visit:**
http://localhost:8501

### **And start scraping Reddit like a pro!**

---

## 📞 Need More Help?

- 📖 **Complete Guide:** See `WEB_FRONTEND_GUIDE.md` for detailed instructions
- 🔧 **Technical Details:** Check `README.md` for developer info
- 💬 **Reddit API Help:** Visit https://www.reddit.com/dev/api/

---

*Happy scraping! 🚀✨*