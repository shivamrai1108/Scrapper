"""
Configuration settings for Reddit Scraper
"""

# Search Settings
MAX_PAGES = 1000  # Maximum number of pages to scrape (for massive searches)
POSTS_PER_PAGE = 100  # Reddit API limit is typically 100 posts per request
MAX_RESULTS = 100000  # Up to 1 lakh (100,000) posts can be searched
DEFAULT_MAX_RESULTS = 2500  # Default when not specified

# Excel Export Settings
EXCEL_FILENAME_PREFIX = "reddit_search_results"
OUTPUT_DIR = "output"

# Reddit API Settings
RATE_LIMIT_DELAY = 0.1  # Seconds between requests (0.1 = 10 requests per second, well within limits)
TIMEOUT = 30  # Request timeout in seconds

# Search Filters
SEARCH_SORT_OPTIONS = ["relevance", "hot", "top", "new", "comments"]
DEFAULT_SORT = "relevance"

# Time filters for search (used with 'top' sort)
TIME_FILTER_OPTIONS = ["all", "year", "month", "week", "day", "hour"]
DEFAULT_TIME_FILTER = "all"

# Subreddit settings
DEFAULT_SUBREDDIT = "all"  # Search across all of Reddit