# EmailBot — Setup Guide

## What it does
Reads your Gmail (filtered by labels / senders), summarises new emails with an AI model
via OpenRouter, and delivers a clean HTML digest newsletter **twice a week** via SMTP.

---

## 0. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/EmailBot.git
cd EmailBot
```

> Replace `YOUR_USERNAME/EmailBot` with your actual repository path.

### Set up a virtual environment (recommended)

**macOS / Linux / WSL**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt / PowerShell)**
```bash
python -m venv .venv
.venv\Scripts\activate
```

You should see `(.venv)` in your prompt. All subsequent `pip` and `python` commands
run inside this isolated environment.

### After cloning — what is NOT in the repo

These files are git-ignored and must be created manually:

| File | Why missing | What to do |
|---|---|---|
| `.env` | Contains secrets | Copy `.env.example` → `.env`, fill in values |
| `credentials/credentials.json` | Google OAuth secret | Download from Google Cloud Console (Step 2) |
| `credentials/token.json` | Auto-generated | Created on first run after OAuth consent |
| `state.json` | Runtime state | Created automatically on first run |

---

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or reuse one)
3. Enable **Gmail API** under *APIs & Services → Library*
4. Go to *APIs & Services → Credentials → Create Credentials → OAuth client ID*
   - Application type: **Desktop app**
5. Download the JSON file, rename it `credentials.json`
6. Place it at `credentials/credentials.json`

> **First run:** a browser window will open for OAuth consent. After you approve,
> a `credentials/token.json` is saved — future runs are silent.

---

## 3. Configure `.env`

Copy the template and fill in your values:

```bash
cp .env.example .env
```

Key settings:

| Variable | Description |
|---|---|
| `GMAIL_LABELS` | Comma-separated Gmail labels to scan (e.g. `INBOX,newsletters`) |
| `GMAIL_SENDER_FILTER` | Optional — only emails from these domains/addresses |
| `OPENROUTER_API_KEY` | Your key from [openrouter.ai/keys](https://openrouter.ai/keys) |
| `OPENROUTER_MODEL` | Any model slug, e.g. `anthropic/claude-3.5-sonnet` |
| `SMTP_HOST` / `SMTP_PORT` | Your SMTP server (Gmail: `smtp.gmail.com:587`) |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | For Gmail, use an **App Password** (not your real password) |
| `SMTP_TO` | Where to deliver the newsletter |
| `SCHEDULE_DAYS` | `0,3` = Monday & Thursday; `1,4` = Tuesday & Friday |
| `SCHEDULE_TIME` | 24h time, e.g. `08:00` |

### Gmail App Password (if using Gmail SMTP)
Account → Security → 2-Step Verification → App Passwords → generate one for "Mail".

---

## 4. Run

### Test immediately (no schedule)
```bash
python main.py --now
```

### Start the scheduler (runs 2× / week indefinitely)
```bash
python main.py
```

---

## 5. File overview

```
EmailBot/
├── main.py           # Scheduler + pipeline orchestration
├── gmail_client.py   # Gmail API: fetch & mark emails
├── summarizer.py     # OpenRouter AI summarization
├── newsletter.py     # HTML rendering + SMTP delivery
├── state.py          # Persist last-run timestamp & processed IDs
├── config.py         # Load all settings from .env
├── requirements.txt
├── .env.example
└── credentials/      # Gmail OAuth files (git-ignored)
    └── credentials.json   ← you place this here
```

---

## 6. Keeping the pipeline running continuously

### What must stay alive

The scheduler is a **long-running Python process**. If it stops, no digest is sent.
Three things must always be in place:

| Layer | Requirement | What breaks if missing |
|---|---|---|
| **Process** | `python main.py` must be running | No emails fetched, no newsletter sent |
| **Gmail OAuth token** | `credentials/token.json` must be valid | Gmail API returns 401, fetch fails |
| **Network + API keys** | Internet access, valid OpenRouter key, valid SMTP credentials | Summarisation or delivery fails |

---

### Process: keep it alive after closing the terminal

By default the process dies when you close the terminal. Use one of these:

**Option A — `nohup` (simplest, Linux/macOS/WSL)**
```bash
nohup python main.py > emailbot.log 2>&1 &
echo $! > emailbot.pid   # save process ID so you can kill it later
```
Stop it later: `kill $(cat emailbot.pid)`

**Option B — Windows Task Scheduler (native Windows)**
1. Open *Task Scheduler → Create Basic Task*
2. Trigger: **At log on** (or at startup)
3. Action: Start a program
   - Program: `C:\path\to\python.exe`
   - Arguments: `main.py`
   - Start in: `C:\Users\bichn\MSBA\Machine Learning\EmailBot`
4. Check "Run whether user is logged on or not"

**Option C — `screen` / `tmux` (interactive, Linux/macOS/WSL)**
```bash
screen -S emailbot
python main.py
# Ctrl+A then D to detach — process keeps running
screen -r emailbot   # reattach later
```

---

### Gmail OAuth token: when it expires and how to refresh

The OAuth token (`credentials/token.json`) contains a **refresh token** that never expires
as long as:

- The Google Cloud project's OAuth consent screen stays in **Testing** or **Production** mode
- You do **not** revoke access at [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
- The `credentials/token.json` file is **not deleted**

The short-lived access token (1 hour) is **refreshed automatically** by the code — no manual
action needed. The refresh token itself is long-lived.

**When you will need to re-authenticate (browser re-opens):**

| Situation | Action |
|---|---|
| `token.json` deleted or corrupted | Delete the file, re-run `python main.py --now` |
| Google revoked access | Re-run `python main.py --now`, approve in browser |
| OAuth app moved to "Testing" with 7-day expiry | Publish the app to Production in Google Cloud Console |
| `credentials.json` replaced | Delete `token.json` and re-authenticate |

> **Important:** If your app is in **Testing** mode in Google Cloud, refresh tokens expire
> after **7 days**. Publish the consent screen to Production to get permanent tokens.

---

### API keys and credentials: what to check if a run silently fails

Check `emailbot.log` (or stdout) for these specific errors:

| Error message | Cause | Fix |
|---|---|---|
| `401 Unauthorized` (Gmail) | Token expired or revoked | Delete `token.json`, re-run with `--now` |
| `403 Forbidden` (Gmail) | Gmail API not enabled or quota exceeded | Check Cloud Console → APIs & Services |
| `AuthenticationError` (OpenRouter) | `OPENROUTER_API_KEY` invalid or out of credits | Renew key / top up at openrouter.ai |
| `SMTPAuthenticationError` | Wrong SMTP password | Re-generate Gmail App Password, update `.env` |
| `SMTPConnectError` | Network issue or firewall blocks port 587 | Check internet connection / firewall rules |
| `FileNotFoundError: credentials.json` | Missing credentials file | Re-download from Google Cloud Console |

---

### Routine maintenance checklist

Run this check every few months to ensure the pipeline stays healthy:

- [ ] **OpenRouter credits** — top up at [openrouter.ai](https://openrouter.ai) before balance hits zero
- [ ] **Gmail App Password** — regenerate if you change your Google account password
- [ ] **`token.json` present** — verify `credentials/token.json` exists and is non-empty
- [ ] **Process is running** — `ps aux | grep main.py` (Linux) or check Task Scheduler (Windows)
- [ ] **`state.json` exists** — if missing, the bot re-processes all emails from scratch (harmless but noisy)
- [ ] **Log file size** — rotate `emailbot.log` if it grows too large

---

## Customisation tips

- **Change schedule:** edit `SCHEDULE_DAYS` and `SCHEDULE_TIME` in `.env`
- **Change AI model:** any model on [openrouter.ai/models](https://openrouter.ai/models) works
- **Add more recipients:** comma-separate values in `SMTP_TO`
- **Filter by label:** create a Gmail filter → assign a label → set `GMAIL_LABELS=yourlabel`
