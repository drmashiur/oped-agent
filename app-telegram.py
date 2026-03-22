import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

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


def load_sources():
    p = Path(SOURCES_FILE)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_seen():
    p = Path(SEEN_FILE)
    if not p.exists():
        return set()
    return set(line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip())


def save_seen(seen_urls):
    Path(SEEN_FILE).write_text("\n".join(sorted(seen_urls)) + "\n", encoding="utf-8")


def same_domain(base_url, candidate_url):
    return urlparse(base_url).netloc == urlparse(candidate_url).netloc


def extract_links_from_section(page_url):
    links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.goto(page_url, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "lxml")

    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        text = a.get_text(" ", strip=True)

        if not same_domain(page_url, href):
            continue
        if len(text) < 20:
            continue
        if href.count("/") < 3:
            continue

        links.append((text, href))

    unique = []
    seen = set()
    for title, url in links:
        if url not in seen:
            unique.append((title, url))
            seen.add(url)

    return unique[:30]


def fetch_article_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"    Failed to fetch article text: {e}")
        return ""

    soup = BeautifulSoup(r.text, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paragraphs if len(p) > 40)

    return text[:20000]


def save_results_to_json(matched, timestamp):
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = (Path(DATA_DIR) / f"matched_{timestamp}.json").resolve()

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(matched, f, ensure_ascii=False, indent=2)

    print(f"\nSaved JSON results to: {filename}")
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

    print(f"Saved CSV results to: {filename}")
    return str(filename)


def escape_markdown_v2(text):
    if text is None:
        return ""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")
    return text


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
        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()
        print("Telegram notification sent successfully.")
        return True
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")
        return False


def send_telegram_message_markdown(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram settings are missing in .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()
        print("Telegram markdown notification sent successfully.")
        return True
    except Exception as e:
        print(f"Failed to send Telegram markdown notification: {e}")
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
    messages = []

    if not matched:
        msg = (
            "Op-Ed Agent Update\n\n"
            "আজ কোনো relevant op-ed article পাওয়া যায়নি।\n\n"
            f"JSON: {json_path}\n"
            f"CSV: {csv_path}"
        )
        messages.append(msg)
        return messages

    header = (
        f"Op-Ed Agent Update\n"
        f"Matched articles found: {len(matched)}\n\n"
    )

    body_lines = []
    for idx, item in enumerate(matched, start=1):
        body_lines.append(f"{idx}. {item['title']}")
        body_lines.append(f"Category: {item['category']}")
        body_lines.append(f"Score: {item['score']}")
        body_lines.append(f"Summary: {item['summary']}")
        body_lines.append(f"URL: {item['url']}")
        body_lines.append("")

    footer = (
        f"Saved JSON: {json_path}\n"
        f"Saved CSV: {csv_path}"
    )

    full_text = header + "\n".join(body_lines) + "\n" + footer
    messages = split_message(full_text)

    return messages


def main():
    sources = load_sources()
    seen_urls = load_seen()

    if not sources:
        print("No source URLs found in sources.txt")
        return

    matched = []

    for source in sources:
        print(f"\nChecking source: {source}")
        try:
            links = extract_links_from_section(source)
        except Exception as e:
            print(f"  Failed to extract links: {e}")
            continue

        for title, url in links:
            if url in seen_urls:
                continue

            print(f"  Reading: {title[:80]}")
            text = fetch_article_text(url)
            seen_urls.add(url)

            if len(text) < 500:
                print("    Skipping: article text too short")
                continue

            try:
                result = classify_article(title, url, text)
            except Exception as e:
                print(f"    Classification failed: {e}")
                continue

            if result.get("relevant"):
                matched_item = {
                    "title": title,
                    "url": url,
                    "category": result.get("primary_category"),
                    "score": result.get("score"),
                    "summary": result.get("bangla_summary"),
                }
                matched.append(matched_item)
                print(f"    MATCH [{result.get('score')}]: {url}")
            else:
                print("    Not relevant")

            time.sleep(1)

    save_seen(seen_urls)

    print("\n=== MATCHED ARTICLES ===")
    for item in matched:
        print(f"\nTitle: {item['title']}")
        print(f"URL: {item['url']}")
        print(f"Category: {item['category']}")
        print(f"Score: {item['score']}")
        print(f"Summary: {item['summary']}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_path = save_results_to_json(matched, timestamp)
    csv_path = save_results_to_csv(matched, timestamp)

    telegram_messages = build_telegram_messages(matched, json_path, csv_path)

    for msg in telegram_messages:
        send_telegram_message(msg)
        time.sleep(1)

    if not matched:
        print("\nNo matched articles found. Empty result files were still saved.")


if __name__ == "__main__":
    main()
