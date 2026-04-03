import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from classifier import classify_article

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36"
}

BASE_DIR = Path(__file__).resolve().parent
SOURCES_FILE = BASE_DIR / "sources.txt"
SEEN_FILE = BASE_DIR / "seen_urls.txt"
DATA_DIR = BASE_DIR / "data"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Load the threshold from .env, defaulting to 50 if it's missing
MIN_SCORE_THRESHOLD = int(os.getenv("MIN_SCORE_THRESHOLD", 50))


def load_sources():
    p = Path(SOURCES_FILE)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def load_seen():
    p = Path(SEEN_FILE)
    if not p.exists():
        return set()
    return set(line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip())


def save_seen(seen_urls):
    Path(SEEN_FILE).write_text("\n".join(sorted(seen_urls)) + "\n", encoding="utf-8")


def fetch_article_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"    Failed to fetch full article text: {e}")
        return ""

    soup = BeautifulSoup(r.text, "lxml")

    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paragraphs if len(p) > 40)

    return text[:20000]


def save_results_to_json(matched, timestamp):
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = (Path(DATA_DIR) / f"matched_{timestamp}.json").resolve()

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(matched, f, ensure_ascii=False, indent=2)

    return str(filename)


def save_results_to_csv(matched, timestamp):
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = (Path(DATA_DIR) / f"matched_{timestamp}.csv").resolve()

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["title", "url", "category", "score", "summary"]
        )
        writer.writeheader()
        writer.writerows(matched)

    return str(filename)


def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram settings are missing in .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }

    try:
        requests.post(url, data=payload, timeout=30).raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")
        return False


def split_message(text, max_length=3500):
    parts = []
    current = ""
    for line in text.splitlines(True):
        if len(current) + len(line) > max_length:
            parts.append(current)
            current = line
        else:
            current += line
    if current:
        parts.append(current)
    return parts


def build_telegram_messages(matched, json_path, csv_path):
    if not matched:
        return []

    header = f"Op-Ed Agent Update\nArticles above threshold ({MIN_SCORE_THRESHOLD}): {len(matched)}\n\n"
    body_lines = []
    
    for idx, item in enumerate(matched, start=1):
        body_lines.append(f"{idx}. {item['title']}")
        body_lines.append(f"Category: {item['category']}")
        body_lines.append(f"Score: {item['score']}/100")
        body_lines.append(f"Summary: {item['summary']}")
        body_lines.append(f"URL: {item['url']}")
        body_lines.append("")

    footer = f"Saved to JSON & CSV locally."
    
    full_text = header + "\n".join(body_lines) + "\n" + footer
    return split_message(full_text)


def main():
    sources = load_sources()
    seen_urls = load_seen()

    if not sources:
        print("No source URLs found in sources.txt")
        return

    matched = []

    for source in sources:
        print(f"\nChecking RSS feed: {source}")
        try:
            feed = feedparser.parse(source)
        except Exception as e:
            print(f"  Failed to parse feed: {e}")
            continue
            
        for entry in feed.entries[:15]:
            title = entry.get('title', 'Unknown Title')
            url = entry.get('link', '')

            if not url or url in seen_urls:
                continue

            print(f"  Evaluating: {title[:80]}")
            
            summary_html = entry.get('summary', '') or entry.get('description', '')
            text_content = BeautifulSoup(summary_html, "lxml").get_text(" ", strip=True)
            
            if len(text_content) < 500:
                full_page_text = fetch_article_text(url)
                if full_page_text:
                    text_content = full_page_text

            if len(text_content) < 300:
                print("    Skipping: article text too short")
                seen_urls.add(url)
                save_seen(seen_urls)
                continue

            try:
                result = classify_article(title, url, text_content)
            except Exception as e:
                print(f"    Classification failed: {e}")
                continue

            seen_urls.add(url)
            save_seen(seen_urls)

            is_relevant = result.get("relevant", False)
            score = result.get("score", 0)

            if is_relevant:
                if score >= MIN_SCORE_THRESHOLD:
                    matched_item = {
                        "title": title,
                        "url": url,
                        "category": result.get("primary_category"),
                        "score": score,
                        "summary": result.get("bangla_summary"),
                    }
                    matched.append(matched_item)
                    print(f"    MATCH [Score: {score}]: Passed threshold!")
                else:
                    print(f"    REJECTED [Score: {score}]: Relevant, but below {MIN_SCORE_THRESHOLD} threshold.")
            else:
                print("    Not relevant")

            time.sleep(1)

    print(f"\n=== MATCHED ARTICLES (>={MIN_SCORE_THRESHOLD}) ===")
    for item in matched:
        print(f"\nTitle: {item['title']} (Score: {item['score']})")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # We only save files and send Telegram messages if we actually matched something above the threshold
    if matched:
        json_path = save_results_to_json(matched, timestamp)
        csv_path = save_results_to_csv(matched, timestamp)
        
        telegram_messages = build_telegram_messages(matched, json_path, csv_path)
        for msg in telegram_messages:
            send_telegram_message(msg)
            time.sleep(1)
    else:
        print(f"\nNo articles met the minimum score threshold of {MIN_SCORE_THRESHOLD}.")


if __name__ == "__main__":
    main()
