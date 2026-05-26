---
title: AI Marketing Engine
emoji: 🚀
colorFrom: green
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: 24/7 Automated AI Marketing Dashboard and Lead Generation
---

# 🚀 AI Marketing Engine

A **24/7 Automated AI Marketing Dashboard and Lead Generation Tool** built with
Streamlit, Python asyncio, Playwright, BeautifulSoup4, and the Groq API.

---

## 📁 Project Structure

```
plugin/
├── app.py               # Main entry point — Streamlit UI + CSS
├── engine.py            # asyncio EngineManager (thread bridge)
├── workers.py           # 5 async background workers
├── groq_engine.py       # Groq key rotator + prompt builders
├── database.py          # SQLite persistence layer
├── ui_settings.py       # Tab 1: Settings and Configuration UI
├── ui_dashboard.py      # Tab 2: Live Dashboard and Logs UI
├── Dockerfile           # HF Spaces Docker build
├── requirements.txt     # Python dependencies
└── .streamlit/
    └── config.toml      # Streamlit theme (White + Green)
```

---

## ⚙️ Setup

### Local
```bash
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

### Hugging Face Spaces
1. Create a new Space with SDK set to **Docker**
2. Connect your GitHub repo or upload files directly
3. Enable **Persistent Storage** in Space Settings
4. Add your Groq API keys inside the app Settings tab

---

## 🔑 Configuration

Add up to **3 Groq API keys** — the engine auto-rotates on rate-limit errors.
Get a free key at [console.groq.com](https://console.groq.com).

Add unlimited plugins with:
- **Plugin Name**
- **Shortlink URL**
- **Description / Selling Point**

Click **Start Engine** to launch all 5 workers concurrently.

---

## 🤖 The 5 Background Workers

| Worker | What It Does |
|--------|-------------|
| **Contact Form Sniper** | Scrapes business contact pages, AI-writes a pitch, submits via Playwright |
| **Blog Comment Bomber** | Scrapes WP plugin blogs, generates contextual comments, auto-submits |
| **YouTube Hijacker** | Finds WP tutorial videos, generates helpful comments, posts via Playwright |
| **Pingback Engine** | Sends XML-RPC pingbacks to competitor WP blogs with your plugin URLs |
| **Reddit Sniper** | Monitors subreddit RSS feeds for trigger words, generates replies |

---

## 📊 Dashboard

- **Metrics row** — live counters for Forms Filled, Comments Posted, Pingbacks Sent
- **Worker grid** — per-worker last-action cards with colour-coded status
- **Terminal console** — real-time timestamped log viewer
- **Export** — download full log as .txt

---

## 🗄️ Persistent Storage

The SQLite database is stored at `/data/marketing_engine.db` inside the container.
Enable **Persistent Storage** in your HF Space settings to keep your plugins,
API keys, and logs across container restarts.

---

## ⚠️ Legal Notice

This tool is provided for educational and research purposes. Users are solely
responsible for ensuring their use complies with the Terms of Service of any
platform targeted and all applicable laws.
