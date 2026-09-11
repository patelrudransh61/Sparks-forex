import urllib.parse
import feedparser
import httpx
from .config import NEWS_LIMIT

def get_news(asset: str) -> list[dict]:
    query = urllib.parse.quote(f"{asset} market")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        response = httpx.get(url, headers={"User-Agent": "AI-Market-Analyzer/1.0"}, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        return [
            {"title": e.get("title", ""), "published": e.get("published", ""), "link": e.get("link", "")}
            for e in feed.entries[:NEWS_LIMIT]
        ]
    except Exception:
        return []
