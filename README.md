# 🚤 Boat Slip Monitor v2.0

**Modern, reliable monitoring for boat slip registration pages**

Complete rewrite with single-container deployment, reliable change detection, and beautiful dark UI.

---

## ✨ Features

- 🔍 **Smart Change Detection** - Detects new forms, keywords, and content changes with zero false positives
- 🚨 **Multi-Channel Notifications** - Telegram, Email, and SMS alerts with priority routing
- 📸 **Automatic Screenshots** - Full-page captures with automatic cleanup
- ⚡ **Real-Time Dashboard** - Live updates via Server-Sent Events (SSE)
- 🌙 **Dark Mode UI** - Beautiful, responsive Next.js interface
- 🐳 **Single Container** - Deploy with one command, no external dependencies
- 💾 **SQLite Database** - Embedded database, no connection issues
- ⏰ **Smart Scheduling** - Time-based checks (3-5 minute intervals)

---

## 🚀 Quick Start

### One Command Deployment

```bash
# 1. Clone repository
git clone <repository-url>
cd boat-slip-monitor

# 2. Start with Docker Compose
docker-compose up -d

# 3. Open browser and complete setup
open http://localhost:3000
```

**That's it!** On first visit:
1. ✅ You'll see the **Setup Screen**
2. ✅ Enter your **Telegram credentials** (required)
3. ✅ Optionally configure **Email notifications**
4. ✅ Review **Advanced settings** or keep defaults
5. ✅ Click **"Complete Setup"**

The monitor will automatically:
- ✅ Initialize database
- ✅ Seed 4 German boat slip URLs
- ✅ Start checking every 3-5 minutes
- ✅ Show live updates in dashboard

---

## 📋 Requirements

- **Docker** 20.10+ and Docker Compose 2.0+
- **1GB RAM** minimum
- **5GB disk** for screenshots and database

---

## ⚙️ Configuration

### Setup Screen (First Time)

On your first visit to `http://localhost:3000`, you'll see a friendly setup wizard:

**1. Telegram Configuration (Required)**
- Message [@BotFather](https://t.me/botfather) on Telegram
- Create a new bot with `/newbot`
- Copy the bot token
- Message your bot, then get your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`

**2. Email Configuration (Optional)**
- SMTP Host (e.g., `smtp.gmail.com`)
- SMTP User & Password (use [App Password](https://myaccount.google.com/apppasswords) for Gmail)
- From & To addresses

**3. Advanced Settings**
- Log Level: DEBUG, INFO, WARNING, ERROR
- Check Intervals (cron format):
  - Working hours (7-17h): `*/5 7-17 * * *` (every 5 min)
  - Off hours (0-6h, 18-23h): `*/3 0-6,18-23 * * *` (every 3 min)
- Screenshot retention & notification settings
- **Semantic Filtering** (enabled by default):
  - `enable_semantic_comparison`: Enable/disable semantic content filtering
  - `track_text_changes`: Monitor text content changes
  - `track_image_changes`: Monitor image changes
  - `track_link_changes`: Monitor link changes

All settings are stored in the database and can be updated anytime via the settings page.

---

## 🎯 How It Works

### Change Detection Strategy

1. **Fetch Page** - Playwright renders JavaScript-heavy pages
2. **Normalize HTML** - Removes timestamps, UUIDs, dynamic content, scripts, styles, CCM cookie consent
3. **Calculate Hash** - SHA-256 of normalized content
4. **Hash Comparison** - Quick check if content changed at all
5. **Semantic Filtering** (NEW!) - If hash changed:
   - Extract semantic content (text, images, links) using BeautifulSoup
   - Compare extracted content between versions
   - Filter out noise (structural changes, attribute changes, whitespace)
   - Only trigger if actual content (text/images/links) changed
6. **Analyze Changes** (if semantic change detected):
   - **Forms Detected** → 🚨 CRITICAL (new form found)
   - **Keywords Matched** → ⚠️ CRITICAL/IMPORTANT (new keywords)
   - **Content Changed** → ℹ️ INFO (regular update)
7. **Notify** - Route to appropriate channels based on priority

**Result:** Zero false positives from cookie banners, dynamic attributes, or structural HTML changes!

### Priority Routing

| Priority | Telegram | Email | SMS | Dashboard |
|----------|----------|-------|-----|-----------|
| CRITICAL | ✅       | ✅    | ✅  | ✅        |
| IMPORTANT| ✅       | ✅    | ❌  | ✅        |
| INFO     | ❌       | ❌    | ❌  | ✅        |

### Keywords Monitored

**Critical** (triggers instant notification):
- warteliste, anmeldung, registrierung
- bewerbung, antrag, formular
- freie plätze, verfügbar, öffnung

**Important** (triggers notification):
- aktualisiert, neu, änderung
- termin, frist, deadline

---

## 🏗️ Architecture

```
Single Container:
├── FastAPI Backend (Python)
│   ├── REST API endpoints
│   ├── APScheduler (cron jobs)
│   ├── Playwright scraper
│   ├── Change detector
│   ├── Notification sender
│   └── SSE event stream
├── SQLite Database (embedded)
│   └── /data/boat_monitor.db
├── Next.js Frontend (static build)
│   └── Served by FastAPI
└── Screenshots Storage
    └── /data/screenshots/
```

**No Redis. No PostgreSQL. No separate containers. Just works.**

---

## 📊 API Endpoints

### REST API

- `GET /api/urls` - List monitored URLs
- `GET /api/checks` - Recent check history
- `GET /api/changes` - Detected changes
- `GET /api/screenshots/{url_id}/{filename}` - Serve screenshots
- `GET /health` - Health check

### Real-Time

- `GET /api/events` - Server-Sent Events stream

---

## 🛠️ Development

### Backend (Python + FastAPI)

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright
playwright install chromium

# Start backend
uvicorn backend.main:app --reload --port 8000
```

### Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open http://localhost:3000

---

## 📦 Monitored URLs (Default)

1. **Konstanz Bootsliegeplatz**
   - https://www.konstanz.de/stadt+gestalten/bauen+_+wohnen/privat+bauen/bootsliegeplatz

2. **Konstanz Serviceportal**
   - https://www.konstanz.de/serviceportal/-/leistungen+von+a-z/.../vbid6001501

3. **Service-BW Leistungen**
   - https://www.service-bw.de/zufi/leistungen/6001501?plz=78467&ags=08335043

4. **Service-BW Online Antrag**
   - https://www.service-bw.de/onlineantraege/onlineantrag?processInstanceId=...

---

## 🔧 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs -f

# Verify Playwright installed
docker exec boat-monitor playwright --version
```

### No notifications

```bash
# Test Telegram token
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Check notification logs
docker-compose logs boat-monitor | grep -i notification
```

### Screenshots not appearing

```bash
# Verify screenshot directory
docker exec boat-monitor ls -lah /data/screenshots/

# Check permissions
docker exec boat-monitor ls -ld /data
```

---

## 🆚 vs. v1.0 (Old System)

| Feature | v2.0 (This) | v1.0 (Old) |
|---------|-------------|------------|
| Containers | 1 | 3 (postgres, redis, monitor) |
| Database | SQLite (embedded) | PostgreSQL (separate) |
| Queue | APScheduler (in-process) | BullMQ + Redis |
| Build Time | ~3 min | ~10 min |
| Memory | 400MB | 700MB |
| False Positives | Zero | Many |
| Deployment | `docker-compose up` | Multiple steps + migrations |
| Data Loss | Never | Frequent (migration issues) |

---

## 📝 License

MIT License - see [LICENSE](LICENSE)

---

**Built with ❤️ for boat slip hunters in Konstanz** 🚤
