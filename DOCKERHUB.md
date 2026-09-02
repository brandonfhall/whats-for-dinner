# What's For Dinner?

A self-hosted meal planning app for households. Plan dinners on a weekly grid, track what's in your freezer and pantry, and optionally let AI suggest the week based on your meal history and preferences.

No authentication, no cloud dependency, no external assets at runtime. Just a single container on your home network.

![What's For Dinner weekly planner view](https://raw.githubusercontent.com/brandonfhall/whats-for-dinner/main/docs/image.png)

---

## Features

- **Meal library** — store every meal your household makes with protein, cuisine, recipe link, notes, and tags for easy-to-make and has-leftovers
- **Weekly planner** — 7-day dinner grid with home cooked, frozen, eat out, and other day types; browse past weeks and view a month calendar
- **Frozen meal inventory** — track homemade frozen meal prep portions with +/- quantity controls
- **Protein inventory** — 14 default protein types auto-seeded; track servings on hand for shopping list calculations
- **Shopping list** — compares what the week's plan needs vs what you have in stock
- **AI suggestions** — Claude or GPT-4o drafts the week in three modes: Mix it up, Play it safe, or On hand (protein/frozen stock only)
- **Custom AI instructions** — free-text dietary preferences and restrictions sent with every AI request
- **Carry-forward** — pin a day so its meal auto-copies to the same day next week
- **Gym and eat-out nights** — configure defaults that apply to every new plan; AI prefers easy meals on gym nights
- **Smart home integration** — `/api/plans/today` returns tonight's dinner as a sentence for Home Assistant TTS
- **Automatic backups** — pre-migration and weekly backups with manual export via API
- **Demo mode** — seed sample data with `DEMO_MODE=true` for quick testing
- **Fully offline** — Alpine.js and Tailwind CSS vendored into the image at build time

---

## Quick Start

### With Traefik

```yaml
services:
  whats-for-dinner:
    image: brandonh317/whats-for-dinner:latest
    restart: unless-stopped
    volumes:
      - dinner-data:/app/data
    env_file:
      - .env
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dinner.rule=Host(`dinner.home`)"
      - "traefik.http.services.dinner.loadbalancer.server.port=8000"
      - "traefik.http.routers.dinner.entrypoints=web"

volumes:
  dinner-data:
```

### Without Traefik

```yaml
services:
  whats-for-dinner:
    image: brandonh317/whats-for-dinner:latest
    restart: unless-stopped
    volumes:
      - dinner-data:/app/data
    ports:
      - "8000:8000"
    env_file:
      - .env

volumes:
  dinner-data:
```

Then visit `http://your-server-ip:8000`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `anthropic` | `anthropic`, `openai`, `openai_compatible`, or `none` — overrides the Settings UI selector if set |
| `AI_API_KEY` | — | API key for the configured provider — overrides the Settings UI value if set |
| `AI_BASE_URL` | — | Endpoint URL for the `openai_compatible` provider (e.g. a self-hosted LiteLLM proxy) — overrides the Settings UI value if set |
| `APP_PORT` | `8000` | Port inside the container |
| `APP_HOSTNAME` | `dinner.home` | Hostname for Traefik routing |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins (comma-separated) |
| `ALLOWED_SUBNETS` | _(all)_ | Restrict access to specific CIDRs (e.g. `192.168.1.0/24`) |
| `DEMO_MODE` | `false` | Seed ~20 sample meals and protein inventory on first startup |

AI is fully optional. The provider, API key, and (for `openai_compatible`) base URL can be configured directly in the Settings tab without touching the server — the key is stored on the server and never returned by the API. Env vars `AI_PROVIDER`, `AI_API_KEY`, and `AI_BASE_URL` take precedence over UI settings if set.

### Example `.env`

```env
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...
ALLOWED_ORIGINS=*
```

---

## Data & Backups

All data is stored in a single SQLite file inside the `dinner-data` Docker volume.

**Backup:**
```bash
docker run --rm -v dinner-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/dinner-backup.tar.gz /data
```

**Restore:**
```bash
docker run --rm -v dinner-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/dinner-backup.tar.gz -C /
```

The app also backs up automatically before database migrations and weekly on startup, and supports manual export through the REST API.

---

## Tags

| Tag | Description |
|---|---|
| `latest` | Most recent build from `main` |
| `YYYYMMDD` | Date-stamped build from `main` |
| `develop` | Latest build from the `develop` branch |

The image rebuilds monthly to pick up base image security patches.

---

## Source & Documentation

Full documentation, API reference, and source code: [github.com/brandonfhall/whats-for-dinner](https://github.com/brandonfhall/whats-for-dinner)
