#!/usr/bin/env python3
"""
Fetches rider rights news from Google News RSS feeds, generates
AI briefings using Claude, and writes to data/news.json.
"""

import json
import os
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError
import anthropic

FEEDS = [
    "https://news.google.com/rss/search?q=motorcycle+rights+legislation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=right+to+repair+motorcycle&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=helmet+law+motorcycle+legislation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=lane+filtering+motorcycle+bill&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=motorcycle+profiling+legislation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=REPAIR+Act+motorcycle&hl=en-US&gl=US&ceid=US:en",
]

AREA_KEYWORDS = {
    "right-to-repair": ["repair act", "right to repair", "telematics", "obd", "diagnostic", "dealer lockout"],
    "helmet-laws": ["helmet law", "helmet mandate", "helmet choice", "helmet repeal", "fmvss 218"],
    "motorcycle-rights": ["lane filtering", "lane splitting", "motorcycle profiling", "ama", "abate", "mrf",
                          "motorcycle rights", "rider rights", "lane filter", "profiling act"],
}

CACHE_FILE = "data/news_cache.json"
OUTPUT_FILE = "data/news.json"
MAX_ARTICLES = 10


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def detect_area(title, summary):
    text = (title + " " + summary).lower()
    for area, keywords in AREA_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return area
    return "motorcycle-rights"


def fetch_feed(url):
    articles = []
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            tree = ET.parse(resp)
        root = tree.getroot()
        channel = root.find("channel")
        if channel is None:
            return articles
        for item in channel.findall("item")[:5]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "#").strip()
            pub_date = item.findtext("pubDate", "").strip()
            desc = item.findtext("description", "").strip()
            source_el = item.find("source")
            source = source_el.text.strip() if source_el is not None and source_el.text else "Syndicated"
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub_date)
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            articles.append({
                "title": title,
                "url": link,
                "source": source,
                "date": date_str,
                "summary": desc[:300].strip(),
                "area": detect_area(title, desc),
            })
    except (URLError, ET.ParseError) as e:
        print(f"Feed error ({url[:60]}): {e}")
    return articles


def generate_briefing(client, title, summary, area):
    area_labels = {
        "right-to-repair": "right to repair motorcycles",
        "helmet-laws": "motorcycle helmet laws and rider choice",
        "motorcycle-rights": "motorcycle rider rights and legislation",
    }
    prompt = f"""You are writing a rider briefing for Easyriders Magazine's policy intelligence platform.
A rider briefing has exactly three short lines:
- IMPACT: One sentence on what this means for American motorcyclists.
- TIMELINE: One sentence on when this matters or when something will happen.
- ACTION: One sentence on what a rider can do about it (specific, not generic).

Topic area: {area_labels.get(area, "motorcycle rights")}
Story: {title}
Context: {summary[:400]}

Respond in this exact JSON format:
{{"impact": "...", "timeline": "...", "action": "..."}}"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        return json.loads(text)
    except Exception as e:
        print(f"Briefing error: {e}")
        return {
            "impact": "This development affects motorcycle rider rights and policy.",
            "timeline": "Monitor this issue for further developments.",
            "action": "Stay informed through the AMA and your state ABATE chapter.",
        }


def main():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    cache = load_cache()

    seen_titles = set()
    raw_articles = []
    for url in FEEDS:
        for a in fetch_feed(url):
            if a["title"] not in seen_titles:
                seen_titles.add(a["title"])
                raw_articles.append(a)

    raw_articles.sort(key=lambda x: x["date"], reverse=True)
    raw_articles = raw_articles[:MAX_ARTICLES]

    final_articles = []
    for i, a in enumerate(raw_articles):
        key = hashlib.md5(a["title"].encode()).hexdigest()
        if key in cache:
            briefing = cache[key]
        else:
            print(f"Generating briefing {i+1}/{len(raw_articles)}: {a['title'][:60]}")
            briefing = generate_briefing(client, a["title"], a["summary"], a["area"])
            cache[key] = briefing

        final_articles.append({
            "id": i + 1,
            "title": a["title"],
            "source": a["source"],
            "date": a["date"],
            "issue_area": a["area"],
            "summary": a["summary"],
            "briefing": briefing,
            "url": a["url"],
        })

    output = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "articles": final_articles,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    save_cache(cache)
    print(f"Done. {len(final_articles)} articles written to {OUTPUT_FILE}.")


if __name__ == "__main__":
    main()
