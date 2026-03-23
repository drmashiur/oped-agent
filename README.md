# 🚀 Oped Agent – Automated News Scraper & Telegram Publisher

An automated Python-based system that collects articles from multiple sources, filters them, and publishes updates directly to a Telegram channel.

This project is designed for **content automation**, especially useful for research platforms, blogs, and news aggregation systems.

---

## 🧠 Overview

This application performs the following tasks:

1. Reads a list of sources (websites/RSS feeds)
2. Extracts new article URLs
3. Avoids duplicates using tracking
4. Optionally classifies articles using AI
5. Sends updates to Telegram automatically
6. Stores processed data for tracking

---

## ⚙️ Tech Stack

* **Python 3**
* **requests** – HTTP requests for static websites
* **BeautifulSoup (bs4)** – HTML parsing
* **Playwright** – Dynamic website scraping (JavaScript support)
* **dotenv** – Environment variable management
* **Telegram Bot API** – Sending messages
* **CSV / JSON** – Data storage
* **Cron** – Task scheduling (automation)

---

## 📂 Project Structure

```
oped-agent/
│
├── app-telegram.py       # Main automation script
├── sources.txt           # List of source URLs
├── seen_urls.txt         # Tracks processed URLs
├── data/                 # Stored article data (CSV/JSON)
├── .env                  # Environment variables (Telegram token, etc.)
├── requirements.txt      # Python dependencies
└── README.md
```

---

## 🔧 Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/drmashiur/oped-agent.git
cd oped-agent
```

---

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```


---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Install Playwright browsers

```bash
python -m playwright install
```

(Optional – install dependencies for Linux)

```bash
python -m playwright install --with-deps
```

---

### 5. Setup environment variables

Create a `.env` file:

```
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```


You can use the env.example for your use


---

### 6. Add sources and output folder

Edit `sources.txt` and add URLs:

```
https://example.com/rss
https://another-source.com
```

create a folder `data` that will store the output data. 

---

## ▶️ Run the Application

For simple output in your pc, run this command. It will not notify to your channel

```bash
python app.py
```


To send notification to your Telegram channel run this:

```bash
python app-telegram.py
```



---

## ⏰ Automation with Cron

Run every hour from 7 AM to 10 PM:

```bash
crontab -e
```

Add:

```cron
0 7-22 * * * cd /home/user/oped-agent && /home/user/oped-agent/.venv/bin/python app-telegram.py >> /home/user/app.log 2>&1
```

---

## 🔁 How It Works

1. Loads sources from `sources.txt`
2. Scrapes article links using:

   * `requests` + `BeautifulSoup`
   * `Playwright` (for dynamic sites)
3. Checks against `seen_urls.txt` to avoid duplicates
4. Optionally classifies content (AI-based)
5. Sends formatted messages to Telegram
6. Saves data into `data/` folder

---

## 📊 Features

* ✅ Fully automated content pipeline
* ✅ Duplicate filtering
* ✅ Supports dynamic websites
* ✅ Telegram integration
* ✅ Scalable for multiple sources
* ✅ Lightweight and customizable

---

## ⚠️ Notes

* Ensure Playwright dependencies are installed on Linux
* Use virtual environment to avoid package conflicts
* Keep `.env` file secure (do not commit it)

---

## 🚀 Use Cases

* News aggregation systems
* Research monitoring tools
* Telegram content automation
* Blog/article discovery pipelines

---

## 👨‍💻 Author

**Dr. Mashiur Rahman**

---

## 📄 License

This project is open-source and can be modified for personal or commercial use.

