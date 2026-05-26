---
title: AI Marketing Engine
emoji: 🚀
colorFrom: green
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: 24/7 Automated AI Marketing Dashboard & Lead Generation
---

# 🚀 AI Marketing Engine

A **24/7 Automated AI Marketing Dashboard & Lead Generation Tool** built with
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
├── ui_settings.py       # Tab 1: Settings & Configuration UI
├── ui_dashboard.py      # Tab 2: Live Dashboard & Logs UI
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
1. Create a new Space → SDK: **Docker**
2. Connect your GitHub repo (or upload files directly)
3. Enable **Persistent Storage** in Space Settings → Storage
4. Add your Groq API keys inside the app's Settings tab

---

## 🔑 Configuration (Tab 1 — Settings)

Add up to **3 Groq API keys** — the engine auto-rotates on rate-limit errors.
Get a free key at [console.groq.com](https://console.groq.com).

Add unlimited plugins with:
- **Plugin Name**
- **Shortlink URL**
- **Description / Selling Point**

Click **🚀 START ENGINE** to launch all 5 workers concurrently.

---

## 🤖 The 5 Background Workers

| Worker | What It Does |
|--------|-------------|
| **Contact Form Sniper** | Scrapes business contact pages, AI-writes a fear+solution pitch, submits via Playwright |
| **Blog Comment Bomber** | Scrapes WP plugin blogs, generates natural contextual comments, auto-submits |
| **YouTube Hijacker** | Finds WP tutorial videos, generates helpful comments, posts via Playwright |
| **Pingback Engine** | Sends XML-RPC pingbacks to competitor WP blogs with your plugin URLs |
| **Reddit Sniper** | Monitors subreddit RSS feeds for trigger words, generates sympathetic replies |

---

## 📊 Dashboard (Tab 2)

- **Metrics row** — live counters for Forms Filled, Comments Posted, Pingbacks Sent
- **Worker grid** — per-worker last-action cards with colour-coded status
- **Terminal console** — real-time timestamped log viewer (auto-refreshes every 8s)
- **Export** — download full log as `.txt`

---

## 🗄️ Persistent Storage

The SQLite database (`marketing_engine.db`) is stored at `/data/marketing_engine.db`
inside the container. Enable **Persistent Storage** in your HF Space settings to
keep your plugins, API keys, and logs across container restarts.

---

## ⚠️ Legal Notice

This tool is provided for educational and research purposes. Users are solely
responsible for ensuring their use complies with the Terms of Service of any
platform targeted and all applicable laws.
