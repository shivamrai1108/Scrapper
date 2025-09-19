# 🌐 Reddit Scraper Web Interface

## 🚀 Quick Start (Super Easy!)

### **Method 1: One-Click Launch (Recommended)**

1. **Download the project** and navigate to the folder
2. **Double-click** on `start_web_app.py` or run:
   ```bash
   python3 start_web_app.py
   ```
3. **That's it!** The web interface will open in your browser automatically

The launcher will:
- ✅ Check your Python version
- ✅ Install required packages automatically
- ✅ Create a sample .env file for you
- ✅ Launch the web interface at `http://localhost:8501`

### **Method 2: Manual Setup**

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Configure Reddit API credentials (see below)

# 3. Launch the web app
streamlit run web_frontend.py
```

---

## 🔑 Reddit API Setup (One-Time)

### **Get Your Free Reddit API Credentials:**

1. **Go to:** https://www.reddit.com/prefs/apps/
2. **Click:** "Create App" or "Create Another App"
3. **Fill out the form:**
   - **Name:** `Reddit Scraper` (or any name you like)
   - **App type:** Select **"script"**
   - **Description:** `Personal Reddit data scraper`
   - **About URL:** Leave blank
   - **Redirect URI:** `http://localhost:8080` (required but not used)

4. **Click "Create app"**
5. **Copy the credentials:**
   - **Client ID:** Found under the app name (short string)
   - **Client Secret:** The longer secret string

### **Configure Your .env File:**

Edit the `.env` file in your project folder:

```env
# Reddit API Credentials
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=RedditScraper/1.0 by YourRedditUsername
```

**That's it!** No Reddit account password needed for basic scraping.

---

## 📱 Web Interface Features

### **🎯 User-Friendly Interface**
- **Sidebar Controls:** Easy-to-use form inputs
- **Real-time Progress:** Watch your search progress live
- **Visual Results:** Charts and graphs for your data
- **One-Click Download:** Get your Excel file instantly

### **🔍 Search Options**

#### **Keywords Tab**
- Enter one keyword per line
- Example:
  ```
  Python
  artificial intelligence
  machine learning
  ```

#### **Basic Settings**
- **Max Results:** 10-1000 posts
- **Sort Method:** 
  - `relevance` - Uses Reddit search (fast, targeted)
  - `hot` - Crawls hot posts (comprehensive)
  - `new` - Latest posts first
  - `top` - Most popular posts
  - `comments` - Most commented posts
- **Subreddit:** `all` or specific like `technology`

#### **Advanced Filters**
- **Days Back:** Filter by post age (0 = all time)
- **Minimum Score:** Filter by Reddit upvotes
- **Minimum Comments:** Posts with enough discussion
- **Engagement Rate:** High-interaction posts only
- **Spam Filter:** Remove low-quality posts
- **Sentiment:** Positive/negative/neutral posts only

### **📊 Results & Visualizations**

#### **Instant Data Visualization**
- **📊 Overview:** Key metrics and stats
- **😊 Sentiment:** Pie charts and sentiment trends
- **🚀 Engagement:** Top posts and engagement analysis
- **📈 Trends:** Community analysis and growth patterns

#### **Data Export**
- **📥 Download Button:** One-click Excel download
- **📋 Preview:** View results before downloading
- **📖 Full Dataset:** Expandable full data view

---

## 🎮 Usage Examples

### **1. Brand Monitoring**
```
Keywords: iPhone, Samsung, Google Pixel
Sort: hot
Days Back: 7
Sentiment: all
```

### **2. Tech Trend Analysis**
```
Keywords: AI, ChatGPT, machine learning
Sort: relevance
Max Results: 100
Min Engagement: 5.0
```

### **3. Product Research**
```
Keywords: your_product_name
Subreddit: all
Days Back: 30
Min Score: 10
Exclude Spam: ✓
```

### **4. Market Sentiment**
```
Keywords: Tesla, electric cars
Sort: top
Sentiment: positive
Min Comments: 5
```

---

## 🔧 Technical Features

### **Enhanced Analytics (All Automatic!)**
- ✅ **Sentiment Analysis** - Positive/negative/neutral classification
- ✅ **Engagement Metrics** - Virality scores and trending analysis
- ✅ **Content Quality** - Spam detection and quality scoring
- ✅ **Keyword Density** - Exact word matching and relevance
- ✅ **Community Analysis** - Subreddit insights

### **Smart Search Capabilities**
- ✅ **Massive Crawling** - Up to 100K posts when needed
- ✅ **Exact Matching** - Word boundary detection
- ✅ **API Integration** - Reddit search + manual crawling
- ✅ **Rate Limiting** - Respects Reddit's API limits

### **Professional Output**
- ✅ **Excel Export** - Comprehensive formatted spreadsheets
- ✅ **50+ Data Columns** - Everything from basic info to advanced metrics
- ✅ **Summary Statistics** - Overview sheets with key insights
- ✅ **Ready for Analysis** - Perfect for business intelligence

---

## 🖥️ System Requirements

### **Minimum Requirements:**
- **Python:** 3.7 or higher
- **RAM:** 2GB+ recommended
- **Storage:** 100MB for the app + space for results
- **Internet:** Stable connection for Reddit API

### **Supported Platforms:**
- ✅ **macOS** (tested)
- ✅ **Windows** 10/11
- ✅ **Linux** (Ubuntu, CentOS, etc.)

---

## 🆘 Troubleshooting

### **Common Issues & Solutions:**

#### **"Reddit API credentials not found"**
- Make sure your `.env` file exists and has correct credentials
- Check that there are no extra spaces in your credentials
- Verify your Reddit app is set to "script" type

#### **"No results found"**
- Try different keywords (broader terms)
- Remove or increase the "Days Back" filter
- Try different sort methods (hot, new, top)
- Check if the subreddit exists and is active

#### **Web app won't start**
- Make sure port 8501 is not already in use
- Try running: `streamlit run web_frontend.py --server.port 8502`
- Check Python version: `python3 --version`

#### **Slow search results**
- This is normal for large searches (10K+ posts)
- The progress bar shows real-time status
- Consider using "relevance" sort for faster results

### **Performance Tips:**
- ✅ Use **"relevance" sort** for fastest results
- ✅ **Start small** (50 results) then scale up
- ✅ **Specific subreddits** search faster than "all"
- ✅ **Recent dates** (7-30 days) process quicker

---

## 🎯 Pro Tips

### **For Best Results:**
1. **Start Broad, Then Filter** - Get many results, then use filters
2. **Combine Keywords Smartly** - Related terms work better together
3. **Use Time Filters** - Recent content often more relevant
4. **Monitor Multiple Subreddits** - Different communities, different insights
5. **Export Early, Export Often** - Save your data as you work

### **Business Intelligence Use Cases:**
- 📈 **Brand Monitoring** - Track mentions and sentiment
- 🔍 **Competitor Analysis** - Compare brand performance
- 📊 **Market Research** - Identify trends and opportunities
- 🎯 **Content Strategy** - Find successful content patterns
- 📱 **Product Feedback** - Gather user opinions and issues

---

## 🚀 Ready to Start?

1. **Run:** `python3 start_web_app.py`
2. **Open:** http://localhost:8501
3. **Enter your keywords** in the sidebar
4. **Click:** "🚀 Start Search"
5. **Download:** Your Excel results!

**Need help?** The web interface includes helpful tooltips and guides throughout the app.

---

*Happy scraping! 🔍✨*