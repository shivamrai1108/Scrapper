#!/usr/bin/env python3
"""
Interactive Reddit Scraper
Easy-to-use interface for Reddit keyword scraping
"""

import sys
import os

# Add the current directory to path to import our modules
sys.path.append(os.path.dirname(__file__))

from reddit_scraper import RedditScraper
from config.config import *


def get_user_input():
    """Get search parameters from user input."""
    print("=" * 60)
    print("REDDIT KEYWORD SCRAPER - INTERACTIVE MODE")
    print("=" * 60)
    
    # Get keywords
    keywords_input = input("\n1. Enter keywords to search for (separate multiple keywords with commas): ")
    keywords = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
    
    if not keywords:
        print("Error: At least one keyword is required!")
        return None
    
    # Get subreddit
    subreddit = input(f"\n2. Enter subreddit to search in (default: 'all' for all subreddits): ").strip()
    if not subreddit:
        subreddit = "all"
    
    # Get sort method
    print(f"\n3. Choose sort method:")
    for i, sort_option in enumerate(SEARCH_SORT_OPTIONS, 1):
        print(f"   {i}. {sort_option}")
    
    try:
        sort_choice = int(input(f"Enter choice (1-{len(SEARCH_SORT_OPTIONS)}, default: 1 for relevance): ") or "1")
        sort_method = SEARCH_SORT_OPTIONS[sort_choice - 1]
    except (ValueError, IndexError):
        sort_method = DEFAULT_SORT
        print(f"Invalid choice, using default: {sort_method}")
    
    # Get time filter (only relevant for 'top' sort)
    time_filter = DEFAULT_TIME_FILTER
    if sort_method == "top":
        print(f"\n4. Choose time filter for 'top' posts:")
        for i, time_option in enumerate(TIME_FILTER_OPTIONS, 1):
            print(f"   {i}. {time_option}")
        
        try:
            time_choice = int(input(f"Enter choice (1-{len(TIME_FILTER_OPTIONS)}, default: 1 for all time): ") or "1")
            time_filter = TIME_FILTER_OPTIONS[time_choice - 1]
        except (ValueError, IndexError):
            time_filter = DEFAULT_TIME_FILTER
            print(f"Invalid choice, using default: {time_filter}")
    
    # Get max results
    try:
        max_results = int(input(f"\n5. Maximum number of results (default: {DEFAULT_MAX_RESULTS}, max: 100,000): ") or str(DEFAULT_MAX_RESULTS))
        max_results = min(max_results, MAX_RESULTS)  # Cap at configured maximum (100,000)
    except ValueError:
        max_results = DEFAULT_MAX_RESULTS
        print(f"Invalid number, using default: {max_results}")
    
    # Get days filter
    days_back = None
    try:
        days_input = input(f"\n6. Filter by days (e.g., 30 for last 30 days, ENTER for all time): ").strip()
        if days_input:
            days_back = int(days_input)
            print(f"Will filter posts from last {days_back} days")
    except ValueError:
        days_back = None
        print("Invalid days input, searching all time")
    
    return {
        'keywords': keywords,
        'subreddit': subreddit,
        'sort': sort_method,
        'time_filter': time_filter,
        'max_results': max_results,
        'days_back': days_back
    }


def main():
    """Main interactive function."""
    try:
        # Get user input
        params = get_user_input()
        if not params:
            return
        
        # Display search parameters
        print("\n" + "=" * 60)
        print("SEARCH PARAMETERS:")
        print("=" * 60)
        print(f"Keywords: {', '.join(params['keywords'])}")
        print(f"Subreddit: r/{params['subreddit']}")
        print(f"Sort: {params['sort']}")
        if params['sort'] == 'top':
            print(f"Time Filter: {params['time_filter']}")
        print(f"Max Results: {params['max_results']}")
        if params['days_back']:
            print(f"Date Filter: Last {params['days_back']} days")
        
        # Confirm search
        confirm = input(f"\nProceed with search? (y/n, default: y): ").strip().lower()
        if confirm and confirm not in ['y', 'yes']:
            print("Search cancelled.")
            return
        
        # Initialize scraper and run search
        scraper = RedditScraper()
        excel_file = scraper.run_search(
            keywords=params['keywords'],
            subreddit=params['subreddit'],
            sort=params['sort'],
            time_filter=params['time_filter'],
            max_results=params['max_results'],
            days_back=params['days_back']
        )
        
        if excel_file:
            print(f"\n✓ Excel file created: {excel_file}")
            
            # Ask if user wants to open the file
            open_file = input("\nOpen the Excel file? (y/n, default: n): ").strip().lower()
            if open_file in ['y', 'yes']:
                try:
                    os.system(f"open '{excel_file}'")  # macOS
                except:
                    print(f"Could not open file automatically. Please open: {excel_file}")
        
    except KeyboardInterrupt:
        print("\n\nSearch cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()