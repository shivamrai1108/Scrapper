#!/usr/bin/env python3
"""
Data Visualization Module for Reddit Scraper
Creates charts and graphs for enhanced analytics
"""

import os
from typing import List, Dict
from datetime import datetime

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd
    from wordcloud import WordCloud
    import numpy as np
    VIZ_LIBRARIES_AVAILABLE = True
except ImportError:
    VIZ_LIBRARIES_AVAILABLE = False
    print("⚠️  Visualization libraries not available. Install with: pip install -r requirements.txt")


class DataVisualizer:
    """Create visualizations for Reddit scraper data."""
    
    def __init__(self, output_dir: str = "output/charts"):
        """Initialize the data visualizer."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        if VIZ_LIBRARIES_AVAILABLE:
            # Set style for better-looking charts
            plt.style.use('seaborn-v0_8')
            sns.set_palette("husl")
    
    def create_sentiment_distribution(self, data: List[Dict], filename: str = None) -> str:
        """Create a pie chart showing sentiment distribution."""
        if not VIZ_LIBRARIES_AVAILABLE or not data:
            return None
        
        try:
            # Extract sentiment data
            sentiments = [post.get('Sentiment', 'Neutral') for post in data]
            sentiment_counts = pd.Series(sentiments).value_counts()
            
            # Create pie chart
            plt.figure(figsize=(10, 8))
            colors = ['#2ecc71', '#f39c12', '#e74c3c']  # Green, Orange, Red
            wedges, texts, autotexts = plt.pie(
                sentiment_counts.values, 
                labels=sentiment_counts.index,
                autopct='%1.1f%%',
                colors=colors,
                explode=(0.05, 0.05, 0.05),
                shadow=True,
                startangle=90
            )
            
            plt.title('Sentiment Distribution of Reddit Posts', fontsize=16, fontweight='bold')
            
            # Add count information
            for i, (sentiment, count) in enumerate(sentiment_counts.items()):
                texts[i].set_text(f'{sentiment}\n({count} posts)')
            
            plt.axis('equal')
            
            # Save chart
            if not filename:
                filename = f"sentiment_distribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
        except Exception as e:
            print(f"Error creating sentiment chart: {e}")
            return None
    
    def create_engagement_timeline(self, data: List[Dict], filename: str = None) -> str:
        """Create a timeline showing engagement over time."""
        if not VIZ_LIBRARIES_AVAILABLE or not data:
            return None
        
        try:
            # Prepare data
            df = pd.DataFrame(data)
            if 'Date' not in df.columns or 'Engagement_Rate' not in df.columns:
                return None
            
            # Convert date and sort
            df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d-%m-%Y %H:%M:%S')
            df = df.sort_values('DateTime')
            
            # Create timeline
            plt.figure(figsize=(14, 8))
            
            # Plot engagement rate over time
            plt.subplot(2, 1, 1)
            plt.plot(df['DateTime'], df['Engagement_Rate'], marker='o', alpha=0.7, linewidth=2)
            plt.title('Engagement Rate Over Time', fontsize=14, fontweight='bold')
            plt.ylabel('Engagement Rate')
            plt.grid(True, alpha=0.3)
            
            # Plot post frequency
            plt.subplot(2, 1, 2)
            post_counts = df.groupby(df['DateTime'].dt.date).size()
            plt.bar(post_counts.index, post_counts.values, alpha=0.7)
            plt.title('Post Frequency by Date', fontsize=14, fontweight='bold')
            plt.ylabel('Number of Posts')
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save chart
            if not filename:
                filename = f"engagement_timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
        except Exception as e:
            print(f"Error creating engagement timeline: {e}")
            return None
    
    def create_word_cloud(self, data: List[Dict], keywords: List[str], filename: str = None) -> str:
        """Create a word cloud from post titles and content."""
        if not VIZ_LIBRARIES_AVAILABLE or not data:
            return None
        
        try:
            # Combine all text
            all_text = []
            for post in data:
                title = post.get('Title', '')
                content = post.get('Post_Content', '')
                all_text.append(f"{title} {content}")
            
            combined_text = ' '.join(all_text)
            
            if not combined_text.strip():
                return None
            
            # Create word cloud
            wordcloud = WordCloud(
                width=1200, 
                height=600,
                background_color='white',
                colormap='viridis',
                max_words=100,
                relative_scaling=0.5,
                random_state=42
            ).generate(combined_text)
            
            # Create plot
            plt.figure(figsize=(15, 8))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.title('Most Common Words in Posts', fontsize=16, fontweight='bold', pad=20)
            
            # Highlight keywords
            if keywords:
                keyword_text = f"Search Keywords: {', '.join(keywords)}"
                plt.figtext(0.5, 0.02, keyword_text, ha='center', fontsize=10, style='italic')
            
            # Save chart
            if not filename:
                filename = f"word_cloud_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
        except Exception as e:
            print(f"Error creating word cloud: {e}")
            return None
    
    def create_quality_metrics_chart(self, data: List[Dict], filename: str = None) -> str:
        """Create charts showing various quality metrics."""
        if not VIZ_LIBRARIES_AVAILABLE or not data:
            return None
        
        try:
            df = pd.DataFrame(data)
            
            # Create subplots
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. Relevance vs Engagement
            if 'Relevance_Points' in df.columns and 'Engagement_Rate' in df.columns:
                scatter = ax1.scatter(df['Relevance_Points'], df['Engagement_Rate'], 
                                    alpha=0.6, c=df.get('Virality_Score', 0), cmap='viridis')
                ax1.set_xlabel('Relevance Points')
                ax1.set_ylabel('Engagement Rate')
                ax1.set_title('Relevance vs Engagement Rate')
                plt.colorbar(scatter, ax=ax1, label='Virality Score')
            
            # 2. Quality Score Distribution
            if 'Quality_Score' in df.columns:
                quality_scores = pd.to_numeric(df['Quality_Score'], errors='coerce')
                ax2.hist(quality_scores.dropna(), bins=20, alpha=0.7, color='skyblue', edgecolor='black')
                ax2.set_xlabel('Quality Score')
                ax2.set_ylabel('Number of Posts')
                ax2.set_title('Content Quality Distribution')
            
            # 3. Spam Likelihood
            if 'Spam_Likelihood' in df.columns:
                spam_counts = df['Spam_Likelihood'].value_counts()
                colors = ['green', 'orange', 'red']
                ax3.bar(spam_counts.index, spam_counts.values, color=colors[:len(spam_counts)])
                ax3.set_xlabel('Spam Likelihood')
                ax3.set_ylabel('Number of Posts')
                ax3.set_title('Spam Detection Results')
            
            # 4. Word Count vs Score
            if 'Word_Count' in df.columns and 'Score' in df.columns:
                ax4.scatter(df['Word_Count'], df['Score'], alpha=0.6, color='coral')
                ax4.set_xlabel('Word Count')
                ax4.set_ylabel('Reddit Score')
                ax4.set_title('Content Length vs Reddit Score')
            
            plt.suptitle('Content Quality Metrics Analysis', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            # Save chart
            if not filename:
                filename = f"quality_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
        except Exception as e:
            print(f"Error creating quality metrics chart: {e}")
            return None
    
    def create_community_analysis(self, data: List[Dict], filename: str = None) -> str:
        """Create charts analyzing different communities."""
        if not VIZ_LIBRARIES_AVAILABLE or not data:
            return None
        
        try:
            df = pd.DataFrame(data)
            
            if 'Community' not in df.columns:
                return None
            
            # Get top communities
            top_communities = df['Community'].value_counts().head(10)
            
            # Create subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            
            # 1. Posts by Community
            top_communities.plot(kind='barh', ax=ax1, color='lightblue')
            ax1.set_title('Posts by Community (Top 10)')
            ax1.set_xlabel('Number of Posts')
            
            # 2. Average Engagement by Community
            if 'Engagement_Rate' in df.columns:
                avg_engagement = df.groupby('Community')['Engagement_Rate'].mean().sort_values(ascending=False).head(10)
                avg_engagement.plot(kind='bar', ax=ax2, color='lightgreen')
                ax2.set_title('Average Engagement Rate by Community (Top 10)')
                ax2.set_ylabel('Average Engagement Rate')
                ax2.tick_params(axis='x', rotation=45)
            
            plt.suptitle('Community Analysis', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            # Save chart
            if not filename:
                filename = f"community_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
        except Exception as e:
            print(f"Error creating community analysis: {e}")
            return None
    
    def create_comprehensive_dashboard(self, data: List[Dict], keywords: List[str], 
                                    output_prefix: str = None) -> List[str]:
        """Create a comprehensive dashboard with multiple visualizations."""
        if not VIZ_LIBRARIES_AVAILABLE or not data:
            return []
        
        created_charts = []
        prefix = output_prefix or f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Create all visualizations
            charts_to_create = [
                ('sentiment_distribution', self.create_sentiment_distribution),
                ('engagement_timeline', self.create_engagement_timeline),
                ('word_cloud', lambda d, f: self.create_word_cloud(d, keywords, f)),
                ('quality_metrics', self.create_quality_metrics_chart),
                ('community_analysis', self.create_community_analysis)
            ]
            
            for chart_name, chart_func in charts_to_create:
                try:
                    filename = f"{prefix}_{chart_name}.png"
                    if chart_name == 'word_cloud':
                        result = chart_func(data, filename)
                    else:
                        result = chart_func(data, filename)
                    
                    if result:
                        created_charts.append(result)
                        print(f"✓ Created {chart_name} chart: {result}")
                except Exception as e:
                    print(f"⚠ Could not create {chart_name}: {e}")
            
            return created_charts
        except Exception as e:
            print(f"Error creating dashboard: {e}")
            return created_charts


# Singleton instance
data_visualizer = DataVisualizer()