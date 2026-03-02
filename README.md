# What's For Dinner? 🍽️

A simple household meal planning webapp. Build a library of meals you actually like, plan the week in a 7-day grid, and optionally let AI draft the plan based on your history.

Designed to run on a home network behind Traefik — no auth, no cloud, no fuss.

---

## Features

- **Meal Library** — track every meal with notes, a recipe link, and flags like ⚡ easy-to-make and 📦 has-leftovers
- **Weekly planner** — a 7-day grid for dinners; click any day to set it as home-cooked, eating out, or unplanned
- **AI suggestions** — Claude or GPT-4o looks at your history and meal library and drafts the week for you, respecting gym nights and eat-out nights
- **Gym nights** — configure which nights you go to the gym; AI will prefer easy-to-make meals on those nights
- **Past weeks** — browse previous plans to jog your memory
- **No build step** — frontend is plain HTML + Alpine.js + Tailwind via CDN

---

## Quick Start

### 1. Copy and configure the environment file

```bash
cp .env.example .env
```

Edit `.env`:

```env
# AI provider: "anthropic" (default) or "openai"
AI_PROVIDER=anthropic

# Anthropic Claude API key
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI key (only needed if AI_PROVIDER=openai)
# OPENAI_API_KEY=sk-...
```

AI is optional — the app works fine without a key, and the UI will tell you clearly if it's not configured.

### 2. Set your Traefik hostname

In `docker-compose.yml`, replace `HOSTNAME_PLACEHOLDER` with the hostname you want Traefik to route to this app:

```yaml
- "traefik.http.routers.dinner.rule=Host(`dinner.home`)"
```

### 3. Start the container

```bash
docker compose up -d
```

The app is served on port `8000`. If you're not using Traefik, you can expose it directly by adding a `ports` section:

```yaml
services:
  whats-for-dinner:
    ports:
      - "8000:8000"
```

Then visit `http://your-server-ip:8000`.

---

## Usage

### Setting up your meal library

Go to **Meal Library** and add the meals you cook regularly. For each meal you can record:

| Field | Description |
|---|---|
| Name | What you call it |
| Type | Home cooked / Eat out / Other |
| ⚡ Easy to make | Low effort — good for after the gym |
| 📦 Has leftovers | Produces extra for the next day |
| Recipe link | URL to the recipe (opens in a new tab) |
| Notes | Anything useful — prep time, variations, etc. |
| Shared ingredients | Notes on ingredient overlap with other meals |

### Planning the week

Click **This Week**. Each day starts as "Not planned." Click a day to set it:

- **Home cooked** — pick a meal from your library
- **Eat out** — type where/what (e.g. "Chipotle", "Thai place")
- **No plan** — leave it unset

### Using AI suggestions

Once you have some meals in the library, click **✨ Suggest with AI**. Claude will look at:
- Your full meal library
- The last 8 weeks of plans
- Your configured gym nights and eat-out nights

It will draft the week and fill in all 7 days. You can then click any day to adjust.

If AI isn't configured, the button will say "✨ AI not configured" and clicking it will take you to Settings where you'll see instructions.

### Configuring gym nights

Go to **Settings** and select your gym nights. These are saved and applied to every new plan — the AI will prefer easy-to-make meals on those nights, and they're shown with a 🏋️ icon in the planner.

You can also configure default eat-out nights, which are pre-set to "Eating out" whenever a new plan is created.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | SQLite (file in a named Docker volume) |
| Frontend | Alpine.js + Tailwind CSS (CDN, no build step) |
| AI | Anthropic Claude `claude-sonnet-4-6` or OpenAI `gpt-4o` |
| Container | Single Docker image, docker-compose |

---

## Project Layout

```
whats-for-dinner/
├── app/
│   ├── main.py           # FastAPI app, static file mount
│   ├── database.py       # SQLAlchemy + SQLite setup
│   ├── models.py         # ORM models (Meal, WeeklyPlan, PlanDay, Setting)
│   ├── schemas.py        # Pydantic request/response schemas
│   └── routers/
│       ├── meals.py      # Meal library CRUD
│       ├── plans.py      # Weekly plan CRUD + day updates
│       ├── ai.py         # AI plan generation + status check
│       └── settings.py   # Key-value settings store
├── static/
│   ├── index.html        # SPA shell
│   └── app.js            # All Alpine.js frontend logic
├── data/                 # SQLite db lives here (volume-mounted, gitignored)
├── .env.example
├── docker-compose.yml
└── Dockerfile
```

---

## API

The backend exposes a REST API at `/api/`. Useful endpoints:

```
GET  /api/meals                    List meal library
POST /api/meals                    Add a meal
PUT  /api/meals/{id}               Update a meal

GET  /api/plans/current            Get (or create) this week's plan
PUT  /api/plans/{id}/days/{0-6}    Update a single day in a plan

GET  /api/ai/status                Check if AI is configured
POST /api/ai/generate              Generate a plan with AI

GET  /api/settings                 Read settings
PUT  /api/settings                 Update settings
```

Interactive docs are available at `http://your-host/docs` (FastAPI's built-in Swagger UI).

---

## Data & Backups

All data is stored in a single SQLite file inside the `dinner-data` Docker volume. To back it up:

```bash
docker run --rm -v dinner-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/dinner-backup.tar.gz /data
```

To restore:

```bash
docker run --rm -v dinner-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/dinner-backup.tar.gz -C /
```
