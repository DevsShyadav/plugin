# 🚀 AI Marketing Engine

A **24/7 Automated AI Marketing Dashboard & Lead Generation Tool** built with Streamlit, Python asyncio, Playwright, BeautifulSoup4, and the Groq API.

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
├── requirements.txt     # Python dependencies
└── .streamlit/
    └── config.toml      # Streamlit theme (White + Green)
```

---

## ⚙️ Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the app
```bash
streamlit run app.py
```

---

## 🔑 Configuration (Tab 1 — Settings)

### API Keys
Add up to **3 Groq API keys**. The engine automatically rotates to the next key on rate-limit (429) errors — ensuring zero downtime.

Get your free API key at [console.groq.com](https://console.groq.com).

### Plugins
Add unlimited plugins with:
- **Plugin Name** — e.g. `SpeedBoost Pro`
- **Shortlink URL** — e.g. `https://bit.ly/speedboost`
- **Description / Selling Point** — used by the AI to match the right plugin to the right context

### Master Switch
Click **🚀 START ENGINE** to launch all 5 workers concurrently.
Click **🛑 STOP ENGINE** for a clean graceful shutdown.

---

## 🤖 The 5 Background Workers

| Worker | What It Does |
|--------|-------------|
| **Contact Form Sniper** | Scrapes business contact pages, uses Groq to write a fear+solution pitch, submits via Playwright |
| **Blog Comment Bomber** | Scrapes WP plugin blogs, generates natural contextual comments, auto-submits |
| **YouTube Hijacker** | Finds recent WP tutorial videos, generates helpful comments, posts via Playwright |
| **Pingback Engine** | Sends XML-RPC pingbacks to competitor WP blogs with your plugin URLs |
| **Reddit Sniper** | Monitors subreddit RSS feeds for trigger words, generates sympathetic replies |

---

## 🛠️ Customisation (TODO markers)

Search for `# TODO` in `workers.py` to find all selector and authentication placeholders:

- **Contact / Blog workers** — update CSS selectors to match your target site's form fields
- **YouTube worker** — inject saved browser cookies for authentication
- **Reddit worker** — configure PRAW (Option A) or Playwright cookies (Option B) in `_post_reddit_reply()`

---

## 📊 Dashboard (Tab 2)

- **Metrics row** — live counters for Forms Filled, Comments Posted, Pingbacks Sent
- **Worker grid** — per-worker last-action cards with colour-coded status
- **Terminal console** — real-time timestamped log viewer (auto-refreshes every 8s)
- **Export** — download full log as `.txt`

---

## 🗄️ Database

SQLite file: `marketing_engine.db` (created automatically on first run)

| Table | Purpose |
|-------|---------|
| `api_keys` | 3 Groq key slots (base64 obfuscated) |
| `plugins` | Plugin registry |
| `activity_logs` | Worker action log (auto-pruned at 500 rows) |
| `metrics` | Running counters |

---

## ⚠️ Legal Notice

This tool is provided for **educational and research purposes**. Users are solely responsible for ensuring their use complies with the Terms of Service of any platform targeted (YouTube, Reddit, WordPress, etc.) and all applicable laws.
