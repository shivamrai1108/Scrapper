#!/usr/bin/env python3
"""
Enhanced Analysis Module for Reddit Scraper
Provides sentiment analysis, engagement metrics, and advanced analytics
"""

import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import Counter
import string

try:
    from textblob import TextBlob
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    ENHANCED_LIBRARIES_AVAILABLE = True
except ImportError:
    ENHANCED_LIBRARIES_AVAILABLE = False
    print("⚠️  Enhanced analysis libraries not available. Install with: pip install -r requirements.txt")


class EnhancedAnalyzer:
    """Enhanced analyzer for Reddit posts with sentiment, engagement, and content analysis."""
    
    def __init__(self):
        """Initialize the enhanced analyzer."""
        self.vader_analyzer = None
        self.tfidf_vectorizer = None
        
        if ENHANCED_LIBRARIES_AVAILABLE:
            try:
                self.vader_analyzer = SentimentIntensityAnalyzer()
                self.tfidf_vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
            except Exception as e:
                print(f"Warning: Could not initialize analyzers: {e}")
    
    def analyze_sentiment(self, text: str) -> Dict:
        """
        Analyze sentiment of text using multiple methods.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with sentiment analysis results
        """
        if not text or not ENHANCED_LIBRARIES_AVAILABLE:
            return {
                'sentiment': 'neutral',
                'confidence': 0.5,
                'polarity': 0.0,
                'subjectivity': 0.0,
                'vader_compound': 0.0,
                'vader_pos': 0.0,
                'vader_neg': 0.0,
                'vader_neu': 1.0
            }
        
        try:
            # TextBlob analysis
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1
            
            # VADER analysis
            vader_scores = self.vader_analyzer.polarity_scores(text)
            
            # Determine overall sentiment
            if polarity > 0.1 and vader_scores['compound'] > 0.1:
                sentiment = 'positive'
                confidence = min(abs(polarity), abs(vader_scores['compound']))
            elif polarity < -0.1 and vader_scores['compound'] < -0.1:
                sentiment = 'negative'
                confidence = min(abs(polarity), abs(vader_scores['compound']))
            else:
                sentiment = 'neutral'
                confidence = 1 - min(abs(polarity), abs(vader_scores['compound']))
            
            return {
                'sentiment': sentiment,
                'confidence': round(confidence, 3),
                'polarity': round(polarity, 3),
                'subjectivity': round(subjectivity, 3),
                'vader_compound': round(vader_scores['compound'], 3),
                'vader_pos': round(vader_scores['pos'], 3),
                'vader_neg': round(vader_scores['neg'], 3),
                'vader_neu': round(vader_scores['neu'], 3)
            }
        except Exception as e:
            print(f"Error in sentiment analysis: {e}")
            return {
                'sentiment': 'neutral',
                'confidence': 0.5,
                'polarity': 0.0,
                'subjectivity': 0.0,
                'vader_compound': 0.0,
                'vader_pos': 0.0,
                'vader_neg': 0.0,
                'vader_neu': 1.0
            }
    
    def calculate_engagement_metrics(self, score: int, comments: int, 
                                   created_time: datetime, upvote_ratio: float = None) -> Dict:
        """
        Calculate comprehensive engagement metrics.
        
        Args:
            score: Post score (upvotes - downvotes)
            comments: Number of comments
            created_time: When the post was created
            upvote_ratio: Ratio of upvotes (0-1)
            
        Returns:
            Dictionary with engagement metrics
        """
        try:
            now = datetime.now()
            age_hours = (now - created_time).total_seconds() / 3600
            age_days = age_hours / 24
            
            # Avoid division by zero
            if age_hours <= 0:
                age_hours = 0.1
            
            # Basic engagement metrics
            score_per_hour = score / age_hours if age_hours > 0 else 0
            comments_per_hour = comments / age_hours if age_hours > 0 else 0
            
            # Engagement rate (combines score and comments)
            total_interactions = score + (comments * 2)  # Weight comments more
            engagement_rate = total_interactions / age_hours if age_hours > 0 else 0
            
            # Virality score (exponential decay based on age)
            decay_factor = math.exp(-age_hours / 24)  # Decay over 24 hours
            virality_score = (score + comments * 3) * decay_factor
            
            # Trending potential (recent high engagement)
            if age_hours <= 6:  # Very recent
                trending_multiplier = 2.0
            elif age_hours <= 24:  # Recent
                trending_multiplier = 1.5
            else:
                trending_multiplier = 1.0
            
            trending_potential = engagement_rate * trending_multiplier
            
            # Quality score (considers upvote ratio if available)
            if upvote_ratio and upvote_ratio > 0:
                quality_score = (score * upvote_ratio + comments) / (age_hours + 1)
            else:
                quality_score = engagement_rate
            
            # Controversy score (high comments, mixed votes)
            if upvote_ratio and score > 0:
                controversy_score = (comments / (score + 1)) * (1 - abs(upvote_ratio - 0.5) * 2)
            else:
                controversy_score = 0
            
            return {
                'engagement_rate': round(engagement_rate, 2),
                'virality_score': round(virality_score, 2),
                'trending_potential': round(trending_potential, 2),
                'quality_score': round(quality_score, 2),
                'controversy_score': round(controversy_score, 3),
                'score_per_hour': round(score_per_hour, 2),
                'comments_per_hour': round(comments_per_hour, 2),
                'age_hours': round(age_hours, 1),
                'age_days': round(age_days, 1)
            }
        except Exception as e:
            print(f"Error calculating engagement metrics: {e}")
            return {
                'engagement_rate': 0,
                'virality_score': 0,
                'trending_potential': 0,
                'quality_score': 0,
                'controversy_score': 0,
                'score_per_hour': 0,
                'comments_per_hour': 0,
                'age_hours': 0,
                'age_days': 0
            }
    
    def analyze_content_quality(self, title: str, content: str) -> Dict:
        """
        Analyze content quality metrics.
        
        Args:
            title: Post title
            content: Post content
            
        Returns:
            Dictionary with content quality metrics
        """
        try:
            # Combine title and content
            full_text = f"{title} {content}".strip()
            
            # Basic metrics
            word_count = len(full_text.split())
            char_count = len(full_text)
            sentence_count = len(re.split(r'[.!?]+', full_text)) - 1
            paragraph_count = len([p for p in full_text.split('\n\n') if p.strip()])
            
            # Readability metrics
            if word_count > 0 and sentence_count > 0:
                avg_words_per_sentence = word_count / sentence_count
                avg_chars_per_word = char_count / word_count
            else:
                avg_words_per_sentence = 0
                avg_chars_per_word = 0
            
            # Content complexity
            punctuation_count = sum(1 for char in full_text if char in string.punctuation)
            punctuation_ratio = punctuation_count / char_count if char_count > 0 else 0
            
            # URLs, mentions, hashtags
            url_count = len(re.findall(r'http[s]?://\S+', full_text))
            mention_count = len(re.findall(r'@\w+', full_text))
            hashtag_count = len(re.findall(r'#\w+', full_text))
            
            # Quality indicators
            has_question = '?' in full_text
            has_exclamation = '!' in full_text
            all_caps_ratio = sum(1 for c in full_text if c.isupper()) / char_count if char_count > 0 else 0
            
            # Content type detection
            content_type = 'text'
            if url_count > 0:
                content_type = 'link'
            elif any(keyword in full_text.lower() for keyword in ['image', 'photo', 'pic', 'screenshot']):
                content_type = 'image'
            elif any(keyword in full_text.lower() for keyword in ['video', 'youtube', 'watch', 'clip']):
                content_type = 'video'
            
            # Overall quality score
            quality_factors = [
                min(word_count / 50, 1),  # Prefer longer content up to 50 words
                min(sentence_count / 3, 1),  # Multiple sentences are better
                1 - min(all_caps_ratio * 5, 1),  # Penalize excessive caps
                min(punctuation_ratio * 10, 1),  # Good punctuation usage
            ]
            content_quality_score = sum(quality_factors) / len(quality_factors)
            
            return {
                'word_count': word_count,
                'char_count': char_count,
                'sentence_count': sentence_count,
                'paragraph_count': paragraph_count,
                'avg_words_per_sentence': round(avg_words_per_sentence, 1),
                'avg_chars_per_word': round(avg_chars_per_word, 1),
                'punctuation_ratio': round(punctuation_ratio, 3),
                'url_count': url_count,
                'mention_count': mention_count,
                'hashtag_count': hashtag_count,
                'has_question': has_question,
                'has_exclamation': has_exclamation,
                'all_caps_ratio': round(all_caps_ratio, 3),
                'content_type': content_type,
                'quality_score': round(content_quality_score, 3)
            }
        except Exception as e:
            print(f"Error analyzing content quality: {e}")
            return {
                'word_count': 0,
                'char_count': 0,
                'sentence_count': 0,
                'paragraph_count': 0,
                'avg_words_per_sentence': 0,
                'avg_chars_per_word': 0,
                'punctuation_ratio': 0,
                'url_count': 0,
                'mention_count': 0,
                'hashtag_count': 0,
                'has_question': False,
                'has_exclamation': False,
                'all_caps_ratio': 0,
                'content_type': 'text',
                'quality_score': 0.5
            }
    
    def detect_spam_indicators(self, title: str, content: str, author: str) -> Dict:
        """
        Detect potential spam indicators.
        
        Args:
            title: Post title
            content: Post content
            author: Post author
            
        Returns:
            Dictionary with spam detection results
        """
        try:
            full_text = f"{title} {content}".lower()
            
            # Spam keywords
            spam_keywords = [
                'buy now', 'click here', 'free money', 'make money fast', 
                'limited time', 'act now', 'guaranteed', 'no scam',
                'work from home', 'earn $', 'get rich', 'miracle',
                'weight loss', 'lose weight fast', 'viagra', 'casino',
                'lottery', 'winner', 'congratulations', 'selected'
            ]
            
            spam_keyword_count = sum(1 for keyword in spam_keywords if keyword in full_text)
            
            # Other spam indicators
            excessive_caps = sum(1 for c in full_text if c.isupper()) / len(full_text) if full_text else 0
            excessive_punctuation = full_text.count('!') + full_text.count('?') > 5
            excessive_numbers = sum(1 for c in full_text if c.isdigit()) / len(full_text) if full_text else 0
            
            # URL spam detection
            url_count = len(re.findall(r'http[s]?://\S+', full_text))
            suspicious_urls = bool(re.search(r'bit\.ly|tinyurl|shortlink', full_text))
            
            # Author indicators
            suspicious_author = (
                author == '[deleted]' or
                len(author) > 20 or
                bool(re.search(r'\d{3,}', author))  # Many numbers in username
            )
            
            # Calculate spam score
            spam_indicators = [
                min(spam_keyword_count / 3, 1),
                min(excessive_caps * 5, 1),
                1 if excessive_punctuation else 0,
                min(excessive_numbers * 10, 1),
                min(url_count / 2, 1),
                1 if suspicious_urls else 0,
                0.3 if suspicious_author else 0
            ]
            
            spam_score = sum(spam_indicators) / len(spam_indicators)
            
            # Determine spam likelihood
            if spam_score > 0.6:
                spam_likelihood = 'high'
            elif spam_score > 0.3:
                spam_likelihood = 'medium'
            else:
                spam_likelihood = 'low'
            
            return {
                'spam_score': round(spam_score, 3),
                'spam_likelihood': spam_likelihood,
                'spam_keyword_count': spam_keyword_count,
                'excessive_caps_ratio': round(excessive_caps, 3),
                'excessive_punctuation': excessive_punctuation,
                'url_count': url_count,
                'suspicious_urls': suspicious_urls,
                'suspicious_author': suspicious_author
            }
        except Exception as e:
            print(f"Error in spam detection: {e}")
            return {
                'spam_score': 0,
                'spam_likelihood': 'low',
                'spam_keyword_count': 0,
                'excessive_caps_ratio': 0,
                'excessive_punctuation': False,
                'url_count': 0,
                'suspicious_urls': False,
                'suspicious_author': False
            }
    
    def calculate_keyword_density(self, text: str, keywords: List[str]) -> Dict:
        """
        Calculate keyword density and related metrics.
        
        Args:
            text: Text to analyze
            keywords: List of keywords to check
            
        Returns:
            Dictionary with keyword analysis
        """
        try:
            if not text:
                return {'total_density': 0, 'keyword_densities': {}, 'keyword_positions': {}}
            
            words = re.findall(r'\b\w+\b', text.lower())
            total_words = len(words)
            
            if total_words == 0:
                return {'total_density': 0, 'keyword_densities': {}, 'keyword_positions': {}}
            
            keyword_densities = {}
            keyword_positions = {}
            total_keyword_occurrences = 0
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                # Count exact matches
                keyword_pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                matches = re.findall(keyword_pattern, text.lower())
                count = len(matches)
                
                if count > 0:
                    density = (count / total_words) * 100
                    keyword_densities[keyword] = round(density, 2)
                    
                    # Find positions (first 3 occurrences)
                    positions = [m.start() for m in re.finditer(keyword_pattern, text.lower())][:3]
                    keyword_positions[keyword] = positions
                    
                    total_keyword_occurrences += count
                else:
                    keyword_densities[keyword] = 0
                    keyword_positions[keyword] = []
            
            total_density = (total_keyword_occurrences / total_words) * 100
            
            return {
                'total_density': round(total_density, 2),
                'keyword_densities': keyword_densities,
                'keyword_positions': keyword_positions,
                'total_words': total_words,
                'total_keyword_occurrences': total_keyword_occurrences
            }
        except Exception as e:
            print(f"Error calculating keyword density: {e}")
            return {'total_density': 0, 'keyword_densities': {}, 'keyword_positions': {}}


# Singleton instance
enhanced_analyzer = EnhancedAnalyzer()