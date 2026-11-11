"""
news/fetchers/

Modular fetchers for news ingestion:
  - RSSNewsFetcher: Ingests RSS 2.0 and Atom feeds
  - CompanyNewsFetcher: AI lab release notes & technical blogs
  - YouTubeNewsFetcher: YouTube channels via official XML RSS feeds
  - TavilyNewsFetcher: Real-time breaking AI news via Tavily AI agent search
"""

from .company_fetcher import CompanyNewsFetcher
from .rss_fetcher import RSSNewsFetcher
from .tavily_news_fetcher import TavilyNewsFetcher
from .youtube_fetcher import YouTubeNewsFetcher

__all__ = [
    "RSSNewsFetcher",
    "CompanyNewsFetcher",
    "YouTubeNewsFetcher",
    "TavilyNewsFetcher",
]

