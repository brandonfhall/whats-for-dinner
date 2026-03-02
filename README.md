# What's For Dinner? 🍽️

A simple household meal planning webapp. Build a library of meals you actually like, plan the week in a 7-day grid, and optionally let AI draft the plan based on your history.

Designed to run on a home network behind Traefik — no auth, no cloud, no fuss.

---

## Features

- **Meal Library** — track every meal with notes, recipe link, protein type, cuisine tag, and flags like ⚡ easy-to-make and 📦 has-leftovers
- **Weekly planner** — a 7-day grid for dinners; click any day to set it as home-cooked, eating out, or unplanned
- **Week notes** — a free-text memo on each week (guests, theme, etc.); auto-saves on blur
- **AI suggestions** — Claude or GPT-4o drafts the week based on your history and library; two modes: 🎲 Mix it up (favour less-used meals) or 🛡️ Play it safe (favour favourites); AI varies both protein and cuisine across the week
- **Gym nights** — configure which nights you go to the gym; AI will prefer easy-to-make meals on those nights
- **📌 Carry-forward** — pin any day so its meal copies to the same day next week automatically
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
# AI provider: "anthropic", "openai", or "none" to disable AI suggestions
AI_PROVIDER=anthropic

# API key for whichever provider is active above
AI_API_KEY=sk-ant-...

# CORS: comma-separated allowed origins, or * for any (default: *)
# Set to your Traefik hostname in production:
# ALLOWED_ORIGINS=https://dinner.home
ALLOWED_ORIGINS=*

# Subnet restriction: comma-separated CIDRs, or unset to allow all clients
# ALLOWED_SUBNETS=192.168.1.0/24,10.0.0.0/8
```

AI is optional — set `AI_PROVIDER=none` to disable it entirely, or leave `AI_API_KEY` blank and the UI will tell you clearly it's not configured.

`ALLOWED_SUBNETS` is also optional. When set, only requests from those CIDR ranges are accepted (useful for locking the app to your LAN). The middleware checks `X-Real-IP` first (set by Traefik), then `X-Forwarded-For`, then the raw socket address.

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
| Protein | Chicken, Beef, Fish, Tofu, etc. — used by AI to vary proteins across the week |
| Cuisine | Italian, Mexican, Asian, etc. — used by AI to avoid back-to-back same cuisines |
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

Once you have some meals in the library, click **✨ Suggest with AI** and pick a mode:

- **🎲 Mix it up** — favours meals you haven't had recently or at all. Good for breaking out of a rut.
- **🛡️ Play it safe** — favours household favourites (high usage count). Good for a low-effort week.

Claude (or GPT-4o) looks at your full meal library, the last 8 weeks of plans, and your configured gym/eat-out nights, then fills in all 7 days. Click any day afterward to adjust.

If AI isn't configured, the button will redirect you to Settings where you'll see setup instructions.

### Carry-forward (📌)

When editing a day, check **📌 Carry forward** to pin that meal or eat-out choice. When the next week's plan is created, any pinned days are automatically copied over — useful for standing weekly meals (e.g. "Taco Tuesday"). Carry-forward only fills days that haven't been explicitly set yet.

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
PUT  /api/plans/{id}/notes         Update week-level notes

GET  /api/ai/status                Check if AI is configured
POST /api/ai/generate              Generate a plan with AI

GET  /api/settings                 Read settings
PUT  /api/settings                 Update settings
```

Interactive docs are available at `http://your-host/docs` (FastAPI's built-in Swagger UI).

---

## Tests

The project has 90 tests covering the meals, plans, settings, AI endpoints, and security middleware. Each test runs against a fresh in-memory SQLite database — the production database is never touched.

### Run locally

You'll need Python 3.12. Create a virtual environment, install both dependency files, and run pytest:

```bash
python3.12 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-test.txt
pytest
```

For a coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

### CI

Tests run automatically on every push and pull request to `main` via GitHub Actions (see [.github/workflows/test.yml](.github/workflows/test.yml)). No API keys are required — all AI calls are mocked.

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
