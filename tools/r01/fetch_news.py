"""
뉴스 수집 Tool
Google News RSS를 사용하여 각 종목의 최신 뉴스를 수집합니다.
"""

import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta

import feedparser
import requests

import fetch_companies


def fetch_company_news(company_name: str, max_articles: int = 5) -> list[dict]:
    query = urllib.parse.quote(company_name)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; StockReportBot/1.0)"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"  [경고] {company_name} 뉴스 수집 실패: {e}", file=sys.stderr)
        return [{"error": str(e)}]

    articles = []
    for entry in feed.entries[:max_articles]:
        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            KST = timezone(timedelta(hours=9))
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(KST).strftime("%Y-%m-%d %H:%M")

        # Google News RSS의 source 추출
        source = ""
        if hasattr(entry, "source") and hasattr(entry.source, "title"):
            source = entry.source.title
        elif hasattr(entry, "tags") and entry.tags:
            source = entry.tags[0].get("term", "")

        articles.append({
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", ""),
            "published": published,
            "source": source,
        })

    return articles


def run(config_path: str = "config.json", output_path: str = ".tmp/news_data.json") -> None:
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    companies = fetch_companies.get_companies_with_fallback(config_path)
    max_articles = config["report"].get("news_articles_per_company", 5)

    results = {}
    for company in companies:
        name = company["name"]
        print(f"  뉴스 수집 중: {name}")
        articles = fetch_company_news(name, max_articles)
        results[name] = articles

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_articles = sum(len(v) for v in results.values() if not (len(v) == 1 and "error" in v[0]))
    print(f"[fetch_news] 완료: {len(results)}개 종목, 총 {total_articles}개 기사 → {output_path}")


if __name__ == "__main__":
    run()
