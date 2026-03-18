import csv
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from classifier import classify_article

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36"
}

SOURCES_FILE = "sources.txt"
SEEN_FILE = "seen_urls.txt"
DATA_DIR = "data"


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


# def extract_links_from_section(page_url):
#     links = []

#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True)
#         # page = browser.new_page()
#         page = browser.new_page(ignore_https_errors=True)
#         page.goto(page_url, wait_until="networkidle", timeout=60000)
#         html = page.content()
#         browser.close()

#     soup = BeautifulSoup(html, "lxml")

#     for a in soup.find_all("a", href=True):
#         href = urljoin(page_url, a["href"])
#         text = a.get_text(" ", strip=True)

#         if not same_domain(page_url, href):
#             continue
#         if len(text) < 20:
#             continue
#         if href.count("/") < 3:
#             continue

#         links.append((text, href))

#     unique = []
#     seen = set()
#     for title, url in links:
#         if url not in seen:
#             unique.append((title, url))
#             seen.add(url)

#     return unique[:30]

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


def save_results_to_json(matched):
    Path(DATA_DIR).mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = Path(DATA_DIR) / f"matched_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(matched, f, ensure_ascii=False, indent=2)

    print(f"\nSaved JSON results to: {filename}")


def save_results_to_csv(matched):
    Path(DATA_DIR).mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = Path(DATA_DIR) / f"matched_{timestamp}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["title", "url", "category", "score", "summary"]
        )
        writer.writeheader()
        writer.writerows(matched)

    print(f"Saved CSV results to: {filename}")


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

    if matched:
        save_results_to_json(matched)
        save_results_to_csv(matched)
    else:
        print("\nNo matched articles found.")


if __name__ == "__main__":
    main()