# 🛩️ SkyOps AI - Drone Operations Coordinator

An AI-powered drone operations coordinator built for Skylark Drones. It manages pilot rosters, drone fleets, mission assignments, and detects conflicts — all through a conversational interface.

**Live Demo:** [Streamlit Cloud Link - Add after deployment]

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)               │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ AI Chat  │  │ Dashboard │  │ Pilots/Drones/   │  │
│  │ Tab      │  │ Tab       │  │ Missions Tabs    │  │
│  └────┬─────┘  └─────┬─────┘  └────────┬─────────┘  │
│       │              │                  │            │
│  ┌────▼──────────────▼──────────────────▼─────────┐  │
│  │            Agent Layer (agent.py)              │  │
│  │  Gemini AI ↔ Function Calling ↔ NL Responses  │  │
│  └────────────────────┬──────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼──────────────────────────┐  │
│  │          Data Engine (data_engine.py)          │  │
│  │  Roster Mgmt │ Matching │ Conflicts │ Assign  │  │
│  └──────────┬────────────────────────┬───────────┘  │
│             │                        │               │
│  ┌──────────▼─────┐  ┌──────────────▼────────────┐  │
│  │  CSV Files     │  │  Google Sheets Sync       │  │
│  │  (fallback)    │  │  (sheets_sync.py)         │  │
│  └────────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Components

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application with 5 tabs: AI Chat, Dashboard, Pilots, Drones, Missions |
| `data_engine.py` | Core business logic: querying, matching, conflict detection, cost calculation |
| `agent.py` | Gemini AI integration: NL understanding, action parsing, response generation |
| `sheets_sync.py` | Google Sheets 2-way sync via gspread + service account |

### Key Design Decisions

- **Gemini 2.0 Flash** for the AI backbone — free, fast, and capable enough for structured data reasoning
- **Session state** for in-memory data management during a session, with Sheets as persistent store
- **Action blocks** embedded in AI responses allow the chat to trigger real data mutations
- **Graceful fallback**: App works fully with CSV files if Google Sheets isn't configured

---

## Setup & Deployment

### 1. Prerequisites
- Python 3.9+
- Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com/app/apikey))
- Google Cloud service account (for Sheets sync)

### 2. Local Development
```bash
pip install -r requirements.txt
streamlit run app.py
```

### 3. Deploy to Streamlit Cloud
1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo, set `app.py` as main file
4. Add secrets in Settings → Secrets (see `secrets.toml.example`)

### 4. Google Sheets Setup
1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable Google Sheets API and Google Drive API
3. Create a Service Account → download JSON key
4. Create a Google Sheet with 3 tabs: `pilot_roster`, `drone_fleet`, `missions`
5. Share the Sheet with the service account email
6. Add credentials to Streamlit secrets

---

## Features

- ✅ Conversational AI interface (Gemini-powered)
- ✅ Pilot roster management with filtering and status updates
- ✅ Drone fleet management with weather compatibility checks
- ✅ Smart pilot-to-mission and drone-to-mission matching (scored)
- ✅ Comprehensive conflict detection (6 types)
- ✅ Budget overrun warnings with cost calculations
- ✅ Urgent reassignment planning
- ✅ Google Sheets 2-way sync
- ✅ Real-time dashboard with KPIs
- ✅ Action logging and audit trail

---

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| Streamlit | Web UI framework |
| Google Gemini 2.0 Flash | AI conversational backbone |
| gspread | Google Sheets API client |
| pandas | Data manipulation |
| python-dateutil | Date parsing |
