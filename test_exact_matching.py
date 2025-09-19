#!/usr/bin/env python3
"""
Test script to demonstrate exact keyword matching
"""

import re

def test_exact_matching():
    """Demonstrate the difference between exact and partial matching."""
    
    # Test data
    test_posts = [
        {"title": "New AI technology breakthrough", "content": "This AI system is amazing"},
        {"title": "How to train your AI model", "content": "Training AI models requires patience"},
        {"title": "I love playing games", "content": "Gaming is my favorite hobby"},
        {"title": "The main character died", "content": "Main characters often have plot armor"},
        {"title": "I use this app daily", "content": "This app is very useful for productivity"},
        {"title": "Apple released new iPhone", "content": "The new iPhone has amazing features"},
        {"title": "Machine learning basics", "content": "Learn machine learning fundamentals"},
        {"title": "Chain of thought reasoning", "content": "Chaining thoughts together helps AI"}
    ]
    
    keyword = "AI"
    
    print("=" * 60)
    print("EXACT vs PARTIAL KEYWORD MATCHING DEMONSTRATION")
    print("=" * 60)
    print(f"Searching for keyword: '{keyword}'")
    print()
    
    print("🔍 PARTIAL MATCHING (OLD METHOD):")
    print("Matches any substring containing the keyword")
    partial_matches = []
    for post in test_posts:
        combined = f"{post['title']} {post['content']}".lower()
        if keyword.lower() in combined:
            partial_matches.append(post)
            print(f"✓ '{post['title']}' - Contains '{keyword}' substring")
    print(f"Total partial matches: {len(partial_matches)}")
    
    print()
    print("🎯 EXACT MATCHING (NEW METHOD):")
    print("Matches only complete words with word boundaries")
    exact_matches = []
    keyword_pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
    for post in test_posts:
        combined = f"{post['title']} {post['content']}".lower()
        if re.search(keyword_pattern, combined):
            exact_matches.append(post)
            print(f"✓ '{post['title']}' - Contains exact word '{keyword}'")
    print(f"Total exact matches: {len(exact_matches)}")
    
    print()
    print("📊 COMPARISON:")
    print(f"Partial matching found: {len(partial_matches)} results")
    print(f"Exact matching found: {len(exact_matches)} results")
    print()
    print("🎯 Benefits of exact matching:")
    print("• More precise results")
    print("• Avoids false positives from partial word matches")
    print("• Better relevance scoring")
    print("• Cleaner, more targeted data")
    print()
    
    # Show which posts were filtered out
    filtered_out = [p for p in partial_matches if p not in exact_matches]
    if filtered_out:
        print("🚫 Posts filtered out by exact matching:")
        for post in filtered_out:
            print(f"   - '{post['title']}' (contained '{keyword}' as part of other words)")
    
    print("=" * 60)

if __name__ == "__main__":
    test_exact_matching()