import csv
import json
import time
from datetime import datetime
from pathlib import Path
import feedparser
import requests
from bs4 import BeautifulSoup
from classifier import classify_article

HEADERS = {"User-Agent": "Mozilla/5.0"}
SOURCES_FILE = "sources.txt"
SEEN_FILE = "seen_urls.txt"
DATA_DIR = "data"

def load_sources():
    p = Path(SOURCES_FILE)
    if not p.exists(): return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]

def load_seen():
    p = Path(SEEN_FILE)
    if not p.exists(): return set()
    return set(line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip())

def save_seen(seen_urls):
    Path(SEEN_FILE).write_text("\n".join(sorted(seen_urls)) + "\n", encoding="utf-8")

def fetch_full_text(url):
    """Fallback to fetch full text if RSS description is too short."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return "\n".join(p for p in paragraphs if len(p) > 40)[:20000]
    except Exception:
        return ""

def main():
    sources = load_sources()
    seen_urls = load_seen()
    matched = []

    for source in sources:
        print(f"\nParsing RSS: {source}")
        feed = feedparser.parse(source)
        
        for entry in feed.entries[:15]: # Process the top 15 latest items per feed
            url = entry.link
            title = entry.title
            
            if url in seen_urls:
                continue
                
            print(f"  Evaluating: {title[:60]}...")
            
            # Use the RSS summary if it's long enough, otherwise fetch the full page
            text_content = BeautifulSoup(entry.get('summary', ''), "lxml").get_text(" ", strip=True)
            if len(text_content) < 500:
                text_content = fetch_full_text(url)
                
            if len(text_content) < 300:
                print("    Skipping: Not enough text content.")
                seen_urls.add(url)
                save_seen(seen_urls)
                continue

            # Classify using the dynamic provider
            result = classify_article(title, url, text_content)
            
            # Save state immediately
            seen_urls.add(url)
            save_seen(seen_urls)

            if result.get("relevant"):
                matched.append({
                    "title": title,
                    "url": url,
                    "category": result.get("primary_category"),
                    "score": result.get("score"),
                    "summary": result.get("bangla_summary")
                })
                print(f"    MATCH [{result.get('score')}]: {result.get('primary_category')}")
            else:
                print("    Not relevant")
            
            time.sleep(1) # Be polite to APIs

    # ... [Keep your JSON and CSV saving logic here] ...
    print(f"\nFinished processing. Found {len(matched)} relevant articles.")

if __name__ == "__main__":
    main()

