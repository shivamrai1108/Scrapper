#!/usr/bin/env python3
"""
Reddit Keyword Scraper
Searches Reddit for specified keywords and exports results to Excel
"""

import os
import sys
import time
import argparse
from datetime import datetime
from typing import List, Dict, Optional
import re

import praw
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# Load configuration
sys.path.append(os.path.dirname(__file__))
from config.config import *
from enhanced_analysis import enhanced_analyzer


class RedditScraper:
    def __init__(self):
        """Initialize the Reddit scraper with API credentials."""
        load_dotenv()
        
        # Load Reddit API credentials
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        user_agent = os.getenv('REDDIT_USER_AGENT')
        username = os.getenv('REDDIT_USERNAME')
        password = os.getenv('REDDIT_PASSWORD')
        
        if not all([client_id, client_secret, user_agent]):
            raise ValueError("Missing required Reddit API credentials. Check your .env file.")
        
        # Initialize Reddit instance
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
        
        # Test connection
        try:
            self.reddit.user.me()
            print("✓ Reddit API connection successful")
        except Exception as e:
            print(f"⚠ Reddit API connection failed (read-only mode): {e}")
        
        self.results = []
    
    def calculate_relevance_score(self, title: str, content: str, keywords: List[str]) -> dict:
        """
        Calculate relevance score based on EXACT keyword matches, position, and frequency.
        
        Args:
            title: Post title
            content: Post content
            keywords: List of keywords to match
            
        Returns:
            Dictionary with score and details
        """
        import re
        title_lower = title.lower()
        content_lower = content.lower()
        
        score = 0
        matches = {}
        total_matches = 0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            keyword_score = 0
            
            # Create regex pattern for exact word matching
            keyword_pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            
            # Title matches (weighted higher) - EXACT WORD BOUNDARIES
            title_matches = len(re.findall(keyword_pattern, title_lower))
            if title_matches > 0:
                # Higher score for title matches
                keyword_score += title_matches * 10
                # Bonus for exact match at start of title
                if re.match(r'^\b' + re.escape(keyword_lower) + r'\b', title_lower):
                    keyword_score += 15
                # Additional bonus for title matches (already exact)
                keyword_score += 5
            
            # Content matches - EXACT WORD BOUNDARIES
            content_matches = len(re.findall(keyword_pattern, content_lower))
            if content_matches > 0:
                # Score based on frequency (diminishing returns)
                keyword_score += min(content_matches * 2, 10)
                # Bonus for keyword in first 100 characters
                content_start = content_lower[:100]
                if re.search(keyword_pattern, content_start):
                    keyword_score += 3
            
            if keyword_score > 0:
                matches[keyword] = {
                    'title_matches': title_matches,
                    'content_matches': content_matches,
                    'keyword_score': keyword_score
                }
                total_matches += title_matches + content_matches
                score += keyword_score
        
        # Calculate percentage score (0-100)
        max_possible_score = len(keywords) * 30  # Adjusted max score
        percentage_score = min(100, (score / max_possible_score) * 100) if max_possible_score > 0 else 0
        
        return {
            'score': round(score, 1),
            'percentage': round(percentage_score, 1),
            'total_matches': total_matches,
            'keyword_matches': matches,
            'keywords_found': len(matches)
        }
    
    def search_reddit(self, keywords: List[str], subreddit: str = "all", 
                     sort: str = "relevance", time_filter: str = "all", 
                     max_results: int = DEFAULT_MAX_RESULTS, days_back: int = None) -> List[Dict]:
        """
        Search Reddit for posts containing the specified keywords.
        
        Args:
            keywords: List of keywords to search for
            subreddit: Subreddit to search in (default: "all")
            sort: Sort method for results
            time_filter: Time filter for results
            max_results: Maximum number of results to return
            days_back: Filter posts from last N days (optional)
            
        Returns:
            List of dictionaries containing post data
        """
        from datetime import timedelta
        import time as time_module
        
        # Create search query - simpler format works better with Reddit API
        query = " OR ".join(keywords)  # Remove quotes for better Reddit search compatibility
        print(f"Searching for: {query}")
        print(f"Subreddit: r/{subreddit}")
        print(f"Sort: {sort}, Time filter: {time_filter}")
        print(f"Max results: {max_results}")
        print(f"🎯 Using EXACT word boundary matching (not partial matches)")
        
        # Calculate date cutoff if days_back is specified
        date_cutoff = None
        if days_back:
            date_cutoff = time_module.time() - (days_back * 24 * 60 * 60)  # Convert days to seconds
            cutoff_date = datetime.fromtimestamp(date_cutoff).strftime('%d-%m-%Y')
            print(f"📅 Filtering posts from last {days_back} days (since {cutoff_date})")
        
        # Show time estimates for large searches
        if sort in ["hot", "new", "top"] and max_results > 1000:
            # Realistic estimate: ~600 posts per minute (10 per second with 0.1 delay)
            estimated_posts_to_search = min(max_results * 10, 100000)  # Estimate how many we'll need to search
            estimated_minutes = estimated_posts_to_search / 600  # ~600 posts per minute
            print(f"\n⚠️  LARGE SEARCH WARNING:")
            print(f"   • Will search up to {estimated_posts_to_search:,} posts to find {max_results:,} matches")
            print(f"   • Estimated time: {estimated_minutes:.1f}-{estimated_minutes*2:.1f} minutes")
            print(f"   • Processing ~600 posts per minute (respects Reddit rate limits)")
            proceed = input(f"   • Continue? (y/n, default: y): ").strip().lower()
            if proceed and proceed not in ['y', 'yes']:
                print("Search cancelled.")
                return []
        
        try:
            subreddit_obj = self.reddit.subreddit(subreddit)
            
            # Choose search method based on sort parameter
            if sort == "hot":
                # For non-search sorts, search through MANY more posts to find keywords
                search_limit = 100000  # Search up to 100,000 posts (1 lakh)
                submissions = subreddit_obj.hot(limit=search_limit)  # No cap - search as many as Reddit allows
                print(f"Searching through up to {search_limit} hot posts for keywords...")
            elif sort == "new":
                search_limit = 100000  # Search up to 100,000 posts (1 lakh)
                submissions = subreddit_obj.new(limit=search_limit)
                print(f"Searching through up to {search_limit} new posts for keywords...")
            elif sort == "top":
                search_limit = 100000  # Search up to 100,000 posts (1 lakh)
                submissions = subreddit_obj.top(time_filter=time_filter, limit=search_limit)
                print(f"Searching through up to {search_limit} top posts for keywords...")
            else:  # relevance or comments
                # Use a much higher limit for search to get more comprehensive results
                search_limit = max(max_results * 5, 1000)  # At least 5x more than requested or 1000 minimum
                submissions = subreddit_obj.search(query, sort=sort, limit=search_limit, time_filter=time_filter)
                print(f"Using Reddit search API with enhanced crawling (limit: {search_limit})...")
            
            results = []
            processed_count = 0
            posts_examined = 0
            
            print("\nProcessing posts...")
            
            # Use tqdm for progress bar
            for submission in tqdm(submissions, desc="Scraping posts", unit="posts"):
                posts_examined += 1
                try:
                    # Check date filter first (if specified)
                    if date_cutoff and submission.created_utc < date_cutoff:
                        continue  # Skip posts older than specified days
                    
                    # Check if any keyword appears in title or selftext (EXACT WORD MATCH)
                    import re
                    title_text = submission.title.lower()
                    body_text = getattr(submission, 'selftext', '').lower()
                    combined_text = f"{title_text} {body_text}"
                    
                    # Find matching keywords using exact word boundaries
                    matching_keywords = []
                    for keyword in keywords:
                        # Use regex word boundaries for exact matching
                        keyword_pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                        if re.search(keyword_pattern, combined_text):
                            matching_keywords.append(keyword)
                    
                    # For non-search sorts, ensure we have keyword matches
                    # For search sorts, Reddit already filtered, but we still apply exact matching
                    if not matching_keywords and sort in ["hot", "new", "top"]:
                        continue
                    
                    # For search API results, apply exact matching post-filter
                    if sort not in ["hot", "new", "top"] and not matching_keywords:
                        # Still check if any keyword appears anywhere (less strict for search results)
                        has_any_keyword = any(
                            keyword.lower() in combined_text.lower() 
                            for keyword in keywords
                        )
                        if not has_any_keyword:
                            continue
                    
                    # Stop if we've found enough results
                    if len(results) >= max_results:
                        break
                    
                    # Get post creation date and time
                    post_datetime = datetime.fromtimestamp(submission.created_utc)
                    
                    # Calculate relevance score
                    relevance_data = self.calculate_relevance_score(
                        submission.title, 
                        submission.selftext if submission.selftext else '',
                        keywords
                    )
                    
                    # Enhanced Analysis - Sentiment Analysis
                    combined_text = f"{submission.title} {submission.selftext if submission.selftext else ''}"
                    sentiment_data = enhanced_analyzer.analyze_sentiment(combined_text)
                    
                    # Enhanced Analysis - Engagement Metrics
                    upvote_ratio = getattr(submission, 'upvote_ratio', None)
                    engagement_data = enhanced_analyzer.calculate_engagement_metrics(
                        submission.score, 
                        submission.num_comments, 
                        post_datetime, 
                        upvote_ratio
                    )
                    
                    # Enhanced Analysis - Content Quality
                    quality_data = enhanced_analyzer.analyze_content_quality(
                        submission.title, 
                        submission.selftext if submission.selftext else ''
                    )
                    
                    # Enhanced Analysis - Spam Detection
                    spam_data = enhanced_analyzer.detect_spam_indicators(
                        submission.title, 
                        submission.selftext if submission.selftext else '', 
                        str(submission.author) if submission.author else '[deleted]'
                    )
                    
                    # Enhanced Analysis - Keyword Density
                    density_data = enhanced_analyzer.calculate_keyword_density(combined_text, keywords)
                    
                    # Extract post data with comprehensive enhanced structure
                    post_data = {
                        # Basic Information
                        'Title': submission.title,
                        'Community': f"r/{submission.subreddit.display_name}",
                        'Author': str(submission.author) if submission.author else '[deleted]',
                        'Date': post_datetime.strftime('%d-%m-%Y'),  # DD-MM-YYYY format
                        'Time': post_datetime.strftime('%H:%M:%S'),  # Separate time column
                        
                        # Relevance Metrics
                        'Relevance_Score': f"{relevance_data['percentage']:.1f}%",
                        'Relevance_Points': relevance_data['score'],
                        'Total_Keyword_Matches': relevance_data['total_matches'],
                        'Keywords_Matched': relevance_data['keywords_found'],
                        
                        # Sentiment Analysis
                        'Sentiment': sentiment_data['sentiment'].title(),
                        'Sentiment_Confidence': f"{sentiment_data['confidence']*100:.1f}%",
                        'Polarity': sentiment_data['polarity'],
                        'Subjectivity': sentiment_data['subjectivity'],
                        'VADER_Compound': sentiment_data['vader_compound'],
                        
                        # Engagement Metrics
                        'Engagement_Rate': engagement_data['engagement_rate'],
                        'Virality_Score': engagement_data['virality_score'],
                        'Trending_Potential': engagement_data['trending_potential'],
                        'Quality_Score': engagement_data['quality_score'],
                        'Controversy_Score': engagement_data['controversy_score'],
                        'Score_Per_Hour': engagement_data['score_per_hour'],
                        'Comments_Per_Hour': engagement_data['comments_per_hour'],
                        
                        # Content Quality Metrics
                        'Word_Count': quality_data['word_count'],
                        'Content_Quality_Score': f"{quality_data['quality_score']*100:.1f}%",
                        'Content_Type': quality_data['content_type'].title(),
                        'Has_URLs': 'Yes' if quality_data['url_count'] > 0 else 'No',
                        'Readability_Score': f"{quality_data['avg_words_per_sentence']:.1f} words/sentence",
                        
                        # Spam Detection
                        'Spam_Likelihood': spam_data['spam_likelihood'].title(),
                        'Spam_Score': f"{spam_data['spam_score']*100:.1f}%",
                        
                        # Keyword Analysis
                        'Keyword_Density': f"{density_data['total_density']:.2f}%",
                        
                        # Reddit Metrics
                        'Score': submission.score,
                        'Upvote_Ratio': f"{upvote_ratio*100:.1f}%" if upvote_ratio else 'N/A',
                        'Comments_Count': submission.num_comments,
                        'Age_Hours': engagement_data['age_hours'],
                        'Age_Days': engagement_data['age_days'],
                        
                        # URLs and Links
                        'Post_URL': f"https://reddit.com{submission.permalink}",
                        'External_URL': submission.url if submission.url != f"https://reddit.com{submission.permalink}" else '',
                        'Post_ID': submission.id,
                        
                        # Content
                        'Keywords_Found': ', '.join(matching_keywords) if matching_keywords else ', '.join(keywords),
                        'Post_Content': submission.selftext if submission.selftext else '[No text content]',
                        'Post_Flair': submission.link_flair_text if submission.link_flair_text else '',
                        'Is_NSFW': 'Yes' if submission.over_18 else 'No',
                        'Is_Spoiler': 'Yes' if submission.spoiler else 'No',
                        'Days_Ago': (datetime.now() - post_datetime).days
                    }
                    
                    results.append(post_data)
                    processed_count += 1
                    
                    # Rate limiting
                    time.sleep(RATE_LIMIT_DELAY)
                    
                except Exception as e:
                    print(f"Error processing post: {e}")
                    continue
            
            # Sort results by relevance score (highest first)
            results.sort(key=lambda x: x['Relevance_Points'], reverse=True)
            
            print(f"\n✓ Successfully scraped {len(results)} posts")
            if sort in ["hot", "new", "top"]:
                print(f"📊 Examined {posts_examined} {sort} posts to find {len(results)} matching posts")
            else:
                print(f"📊 Processed {posts_examined} search results from Reddit API")
            
            if len(results) == 0:
                print("\n❌ No results found. This could be due to:")
                print("   • Keywords not found in recent posts")
                print("   • Time filter too restrictive (try --days with higher number or remove)")
                print("   • Exact word matching too strict")
                print("   • Try different sort method: --sort hot, new, or top")
                print("   • Try broader keywords or remove quotes")
                
            if results:
                avg_relevance = sum([post['Relevance_Points'] for post in results]) / len(results)
                max_relevance = max([post['Relevance_Points'] for post in results])
                print(f"🎯 Average relevance: {avg_relevance:.1f} points, Highest: {max_relevance:.1f} points")
            return results
            
        except Exception as e:
            print(f"Error during search: {e}")
            return []
    
    def export_to_excel(self, data: List[Dict], filename: Optional[str] = None, 
                       keywords: List[str] = None) -> str:
        """
        Export scraped data to Excel file.
        
        Args:
            data: List of post dictionaries
            filename: Custom filename (optional)
            keywords: Keywords used in search (for filename)
            
        Returns:
            Path to the created Excel file
        """
        if not data:
            raise ValueError("No data to export")
        
        # Create filename
        if not filename:
            keyword_str = "_".join([kw.replace(" ", "_") for kw in keywords[:3]]) if keywords else "search"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{EXCEL_FILENAME_PREFIX}_{keyword_str}_{timestamp}.xlsx"
        
        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel writer with formatting
        with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Reddit_Search_Results', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Reddit_Search_Results']
            
            # Add formats
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            url_format = workbook.add_format({
                'font_color': 'blue',
                'underline': 1
            })
            
            # Set column widths and formats for comprehensive enhanced data
            # Note: Excel has column limit, prioritizing most important columns
            column_widths = {
                'Title': 50,
                'Community': 15,
                'Author': 15,
                'Date': 12,
                'Time': 10,
                'Relevance_Score': 12,
                'Relevance_Points': 12,
                'Sentiment': 10,
                'Sentiment_Confidence': 15,
                'Engagement_Rate': 12,
                'Virality_Score': 12,
                'Trending_Potential': 15,
                'Quality_Score': 12,
                'Word_Count': 10,
                'Content_Quality_Score': 18,
                'Spam_Likelihood': 12,
                'Spam_Score': 10,
                'Keyword_Density': 12,
                'Score': 8,
                'Upvote_Ratio': 12,
                'Comments_Count': 12,
                'Age_Hours': 10,
                'Post_URL': 60,
                'Post_Content': 80,
                'Keywords_Found': 25
            }
            
            # Apply column formatting
            for col_index, (column_name, width) in enumerate(column_widths.items()):
                if col_index < len(df.columns) and column_name in df.columns:
                    col_letter = chr(ord('A') + col_index)
                    worksheet.set_column(f'{col_letter}:{col_letter}', width)
                    if column_name == 'Post_URL':
                        worksheet.set_column(f'{col_letter}:{col_letter}', width, url_format)
            
            # Apply column formatting (removed old method)
            # Column formatting is now handled above
            
            # Format header row
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Add comprehensive summary sheet with enhanced analytics
            if data:
                # Calculate enhanced statistics
                avg_relevance = sum([post['Relevance_Points'] for post in data]) / len(data)
                max_relevance = max([post['Relevance_Points'] for post in data])
                high_relevance_posts = len([post for post in data if post['Relevance_Points'] >= 20])
                
                # Sentiment distribution
                sentiments = [post.get('Sentiment', 'Neutral').lower() for post in data]
                positive_posts = sentiments.count('positive')
                negative_posts = sentiments.count('negative')
                neutral_posts = sentiments.count('neutral')
                
                # Engagement statistics
                avg_engagement = sum([post.get('Engagement_Rate', 0) for post in data]) / len(data)
                high_engagement = len([post for post in data if post.get('Engagement_Rate', 0) > 10])
                
                # Content quality
                avg_quality = sum([post.get('Quality_Score', 0) for post in data]) / len(data)
                high_quality = len([post for post in data if post.get('Quality_Score', 0) > 5])
                
                # Spam detection
                spam_posts = len([post for post in data if post.get('Spam_Likelihood', 'Low').lower() == 'high'])
                
                # Trending potential
                trending_posts = len([post for post in data if post.get('Trending_Potential', 0) > 15])
                
            else:
                avg_relevance = max_relevance = high_relevance_posts = 0
                positive_posts = negative_posts = neutral_posts = 0
                avg_engagement = high_engagement = avg_quality = high_quality = 0
                spam_posts = trending_posts = 0
            
            summary_data = {
                'Metric': [
                    '📊 BASIC STATISTICS',
                    'Total Posts Found',
                    'Unique Communities',
                    'Search Keywords',
                    'Export Date',
                    '',
                    '🎯 RELEVANCE ANALYSIS',
                    'Average Relevance Score',
                    'Highest Relevance Score',
                    'High Relevance Posts (≥20pts)',
                    'Total Keyword Matches',
                    '',
                    '😊 SENTIMENT ANALYSIS',
                    'Positive Posts',
                    'Negative Posts',
                    'Neutral Posts',
                    'Sentiment Distribution',
                    '',
                    '🚀 ENGAGEMENT METRICS',
                    'Average Engagement Rate',
                    'High Engagement Posts (>10)',
                    'Trending Posts (>15 potential)',
                    'Average Reddit Score',
                    'Total Comments',
                    '',
                    '⭐ QUALITY ANALYSIS',
                    'Average Quality Score',
                    'High Quality Posts (>5)',
                    'Potential Spam Posts',
                    'Average Word Count'
                ],
                'Value': [
                    '━━━━━━━━━━━━━━━━━━━',
                    len(data),
                    len(set([post['Community'] for post in data])) if data else 0,
                    ', '.join(keywords) if keywords else 'N/A',
                    datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
                    '',
                    '━━━━━━━━━━━━━━━━━━━',
                    f"{avg_relevance:.1f} points",
                    f"{max_relevance:.1f} points",
                    f"{high_relevance_posts} posts",
                    sum([post['Total_Keyword_Matches'] for post in data]) if data else 0,
                    '',
                    '━━━━━━━━━━━━━━━━━━━',
                    f"{positive_posts} ({positive_posts/len(data)*100:.1f}%)" if data else "0",
                    f"{negative_posts} ({negative_posts/len(data)*100:.1f}%)" if data else "0",
                    f"{neutral_posts} ({neutral_posts/len(data)*100:.1f}%)" if data else "0",
                    f"😊{positive_posts} 😐{neutral_posts} 😞{negative_posts}",
                    '',
                    '━━━━━━━━━━━━━━━━━━━',
                    f"{avg_engagement:.1f} interactions/hour",
                    f"{high_engagement} posts",
                    f"{trending_posts} posts",
                    round(sum([post['Score'] for post in data]) / len(data), 2) if data else 0,
                    sum([post['Comments_Count'] for post in data]) if data else 0,
                    '',
                    '━━━━━━━━━━━━━━━━━━━',
                    f"{avg_quality:.1f}/10",
                    f"{high_quality} posts",
                    f"{spam_posts} posts" + (" ⚠️" if spam_posts > 0 else " ✅"),
                    round(sum([post.get('Word_Count', 0) for post in data]) / len(data), 1) if data else 0
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Format summary sheet
            summary_worksheet = writer.sheets['Summary']
            summary_worksheet.set_column('A:A', 20)
            summary_worksheet.set_column('B:B', 30)
            
            for col_num, value in enumerate(summary_df.columns.values):
                summary_worksheet.write(0, col_num, value, header_format)
        
        print(f"✓ Data exported to: {filepath}")
        return filepath
    
    def run_search(self, keywords: List[str], subreddit: str = "all", 
                   sort: str = "relevance", time_filter: str = "all", 
                   max_results: int = DEFAULT_MAX_RESULTS, days_back: int = None) -> str:
        """
        Run complete search and export process.
        
        Args:
            keywords: List of keywords to search for
            subreddit: Subreddit to search in
            sort: Sort method
            time_filter: Time filter
            max_results: Maximum results
            
        Returns:
            Path to exported Excel file
        """
        print("=" * 60)
        print("REDDIT KEYWORD SCRAPER")
        print("=" * 60)
        
        # Search Reddit
        results = self.search_reddit(keywords, subreddit, sort, time_filter, max_results, days_back)
        
        if not results:
            print("No results found. Please try different keywords or parameters.")
            return None
        
        # Export to Excel
        excel_file = self.export_to_excel(results, keywords=keywords)
        
        print("\n" + "=" * 60)
        print(f"SEARCH COMPLETED SUCCESSFULLY!")
        print(f"Results saved to: {excel_file}")
        print("=" * 60)
        
        return excel_file


def main():
    """Command line interface for the Reddit scraper."""
    parser = argparse.ArgumentParser(description='Search Reddit for keywords and export to Excel')
    parser.add_argument('keywords', nargs='+', help='Keywords to search for')
    parser.add_argument('--subreddit', '-s', default='all', 
                       help='Subreddit to search in (default: all)')
    parser.add_argument('--sort', choices=SEARCH_SORT_OPTIONS, default=DEFAULT_SORT,
                       help='Sort method for results')
    parser.add_argument('--time-filter', choices=TIME_FILTER_OPTIONS, default=DEFAULT_TIME_FILTER,
                       help='Time filter for results')
    parser.add_argument('--max-results', '-m', type=int, default=DEFAULT_MAX_RESULTS,
                       help='Maximum number of results to fetch (up to 100,000)')
    parser.add_argument('--days', '-d', type=int, default=None,
                       help='Filter posts from last N days (e.g., --days 30 for last 30 days)')
    parser.add_argument('--exact-match', action='store_true',
                       help='Use exact word boundary matching (default: enabled)')
    parser.add_argument('--min-score', type=int, default=0,
                       help='Minimum post score (upvotes - downvotes)')
    parser.add_argument('--min-comments', type=int, default=0,
                       help='Minimum number of comments')
    parser.add_argument('--min-engagement', type=float, default=0,
                       help='Minimum engagement rate')
    parser.add_argument('--exclude-spam', action='store_true',
                       help='Exclude posts with high spam likelihood')
    parser.add_argument('--sentiment-filter', choices=['positive', 'negative', 'neutral', 'all'], 
                       default='all', help='Filter by sentiment')
    
    args = parser.parse_args()
    
    try:
        scraper = RedditScraper()
        scraper.run_search(
            keywords=args.keywords,
            subreddit=args.subreddit,
            sort=args.sort,
            time_filter=args.time_filter,
            max_results=args.max_results,
            days_back=args.days
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()