# 🔍 Reddit Keyword Scraper - Web Interface

**NEW: Easy-to-use web interface with advanced analytics!**

A powerful Reddit data mining tool with a user-friendly web interface. Search Reddit posts, analyze sentiment, track engagement metrics, and export comprehensive Excel reports. Features both web UI and command-line interfaces for maximum flexibility.

## ✨ Features

### 🌐 **Web Interface (NEW!)**
- 🖥️ **Browser-based UI** - No coding required, point and click
- 📊 **Real-time Analytics** - Live sentiment analysis and engagement metrics
- 📱 **Interactive Visualizations** - Charts, graphs, and data insights
- 🎛️ **Advanced Filters** - Score, engagement, sentiment, spam filtering
- 📥 **One-Click Export** - Download Excel files instantly
- ⚡ **Massive Crawling** - Search up to 100,000 posts

### 🔍 **Core Search Features**
- 🎯 **Multi-keyword Search** - Search for multiple keywords simultaneously
- 🌍 **Subreddit Targeting** - Search specific communities or all of Reddit
- 📈 **Flexible Sorting** - Relevance, hot, new, top, most commented
- 📅 **Time Filtering** - Filter by post age (last N days)
- 🎪 **Exact Word Matching** - Precise keyword detection with word boundaries

### 📊 **Advanced Analytics (Automatic)**
- 😊 **Sentiment Analysis** - Positive/negative/neutral classification with confidence
- 🚀 **Engagement Metrics** - Virality scores, trending potential, engagement rates
- ⭐ **Content Quality** - Readability scores, spam detection, quality analysis
- 🏷️ **Keyword Density** - Relevance scoring and keyword frequency analysis
- 🏘️ **Community Insights** - Subreddit analysis and community patterns

## 🚀 Quick Start (Web Interface)

**The easiest way to get started:**

1. **Download/clone** this repository
2. **Run the launcher:**
   ```bash
   python3 start_web_app.py
   ```
3. **That's it!** Your browser will open with the web interface

The launcher automatically:
- ✅ Checks Python version
- ✅ Installs required packages
- ✅ Creates sample .env file
- ✅ Launches web app at http://localhost:8501

## Tech Stack

- **Language**: Python 3.7+
- **Main Libraries**:
  - `praw` - Reddit API wrapper
  - `pandas` - Data manipulation and analysis
  - `openpyxl` & `xlsxwriter` - Excel file creation and formatting
  - `tqdm` - Progress bars
  - `python-dotenv` - Environment variable management

## Installation

### 1. Clone or Download

```bash
git clone <your-repo-url>
cd reddit-scraper
```

### 2. Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Reddit API Setup

1. **Create Reddit App**:
   - Go to https://www.reddit.com/prefs/apps
   - Click "Create App" or "Create Another App"
   - Choose "script" as the app type
   - Fill in the required fields:
     - **Name**: Your app name (e.g., "Reddit Scraper")
     - **Description**: Brief description
     - **Redirect URI**: `http://localhost:8080` (not used but required)

2. **Get Credentials**:
   - **Client ID**: Found under the app name (short string)
   - **Client Secret**: The longer secret string
   - **User Agent**: Should be `AppName/Version by YourUsername`

3. **Create Environment File**:
   ```bash
   cp .env.template .env
   ```
   
   Edit `.env` with your credentials:
   ```
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USER_AGENT=RedditScraper/1.0 by YourUsername
   
   # Optional: For higher rate limits
   REDDIT_USERNAME=your_reddit_username
   REDDIT_PASSWORD=your_reddit_password
   ```

## Usage

### Interactive Mode (Recommended for Beginners)

```bash
python run_scraper.py
```

This will guide you through:
1. Entering keywords to search for
2. Choosing subreddit (or all of Reddit)
3. Selecting sort method
4. Setting maximum results
5. Automatic Excel export

### Command Line Mode

```bash
# Basic search
python reddit_scraper.py "keyword1" "keyword2"

# Search specific subreddit
python reddit_scraper.py "AI" "machine learning" --subreddit technology

# Sort by top posts from the last week
python reddit_scraper.py "python programming" --sort top --time-filter week

# Limit results
python reddit_scraper.py "crypto" --max-results 500

# Multiple options
python reddit_scraper.py "iPhone" "Android" --subreddit all --sort hot --max-results 1000
```

#### Command Line Options

- `keywords`: Keywords to search for (required)
- `--subreddit, -s`: Subreddit to search (default: all)
- `--sort`: Sort method - relevance, hot, top, new, comments (default: relevance)
- `--time-filter`: Time filter for 'top' sort - all, year, month, week, day, hour (default: all)
- `--max-results, -m`: Maximum results to fetch (default: 2500)

## Output Data

The Excel file contains two sheets:

### Main Sheet: "Reddit_Search_Results"
- **Title**: Post title
- **Subreddit**: Subreddit name
- **Author**: Post author
- **Score**: Post score (upvotes - downvotes)
- **Upvote_Ratio**: Percentage of upvotes
- **Comments_Count**: Number of comments
- **Created_UTC**: When the post was created
- **Post_URL**: Direct link to the post
- **Post_ID**: Unique Reddit post ID
- **Keywords_Found**: Which keywords were found
- **Selftext**: Post content (first 500 characters)
- **Is_NSFW**: Whether post is marked NSFW
- **Is_Spoiler**: Whether post is marked as spoiler
- **Post_Flair**: Post flair text

### Summary Sheet
- Total posts found
- Unique subreddits
- Search keywords used
- Export date and time
- Average post score
- Total comments across all posts

## Examples

### Example 1: Technology News
```bash
python reddit_scraper.py "artificial intelligence" "machine learning" "deep learning" --subreddit technology --sort hot --max-results 1000
```

### Example 2: Gaming Discussion
```bash
python reddit_scraper.py "PlayStation 5" "Xbox" "Nintendo Switch" --subreddit gaming --sort top --time-filter week
```

### Example 3: Investment Research
```bash
python reddit_scraper.py "Tesla stock" "TSLA" --subreddit investing --sort relevance --max-results 500
```

## Configuration

You can modify `config/config.py` to change default settings:

- `MAX_PAGES`: Maximum pages to scrape (default: 25)
- `POSTS_PER_PAGE`: Posts per page (default: 100)
- `RATE_LIMIT_DELAY`: Delay between requests (default: 1 second)
- `EXCEL_FILENAME_PREFIX`: Excel file naming prefix

## Troubleshooting

### Common Issues

1. **"Missing required Reddit API credentials"**
   - Ensure your `.env` file is properly configured
   - Double-check your Reddit app credentials

2. **"403 Forbidden" errors**
   - Your Reddit app might be suspended
   - Check if your user agent string is properly formatted
   - Ensure you're not making too many requests too quickly

3. **"No results found"**
   - Try broader keywords
   - Check if the subreddit exists and is accessible
   - Try different sort methods

4. **Rate limiting issues**
   - Increase `RATE_LIMIT_DELAY` in config
   - Add Reddit username/password to `.env` for higher limits

### Performance Tips

- Use specific subreddits instead of "all" for faster searches
- Limit results when testing (use `--max-results 100`)
- Use "relevance" sort for keyword-focused results
- Use "hot" or "top" sort for popular content

## File Structure

```
reddit-scraper/
├── reddit_scraper.py      # Main scraper script
├── run_scraper.py         # Interactive interface
├── requirements.txt       # Python dependencies
├── .env.template         # Environment template
├── .env                  # Your credentials (create this)
├── README.md            # This file
├── config/
│   └── config.py        # Configuration settings
└── output/              # Excel files saved here
    └── *.xlsx          # Generated Excel files
```

## Rate Limits

Reddit API has rate limits:
- **Authenticated**: 60 requests per minute
- **Unauthenticated**: 10 requests per minute

The scraper includes automatic rate limiting to stay within these bounds.

## Legal and Ethical Considerations

- ✅ Uses official Reddit API
- ✅ Respects Reddit's rate limits
- ✅ Only accesses public data
- ⚠️ Always follow Reddit's Terms of Service
- ⚠️ Be respectful of communities and users
- ⚠️ Don't use for spam or harassment

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is provided as-is for educational and research purposes. Please ensure compliance with Reddit's Terms of Service and API guidelines.

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Ensure all dependencies are installed correctly
3. Verify your Reddit API credentials
4. Check Reddit's API status

---

**Happy Scraping!** 🚀