# What's For Dinner?

A self-hosted household meal planning webapp. Build a library of meals you actually like, plan the week in a 7-day grid, and let Claude or GPT-4o draft the plan for you based on your history.

Designed for home networks — no auth, no cloud, no fuss.

![What's For Dinner weekly planner view](https://raw.githubusercontent.com/brandonfhall/whats-for-dinner/main/docs/image.png)

---

## Features

- **Meal library** — name, type, protein, cuisine, recipe link, notes, ⚡ easy-to-make, 📦 has-leftovers
- **Frozen meal inventory** — track homemade frozen meal prep portions with +/- quantity controls
- **Protein inventory** — database-driven protein stock tracking (14 defaults auto-seeded); monitor what's on hand
- **Weekly planner** — 7-day dinner grid; set each day to home-cooked, frozen, eat out, or unplanned
- **Shopping list** — read-only view comparing planned meal needs vs current inventory
- **AI suggestions** — Claude or GPT-4o drafts the week from your library and history; three modes: 🎲 Mix it up / 🛡️ Play it safe / 📦 On hand (only meals with available stock)
- **Gym nights** — AI prefers easy meals on nights you configure as gym nights
- **📌 Carry-forward** — pin a day so its meal copies to the same day next week automatically
- **Week notes** — free-text memo per week (guests, themes, etc.)
- **Offline-capable** — Alpine.js and Tailwind CSS vendored into the image; no CDN or internet access required at runtime

---

## Quick Start

### docker-compose (with Traefik)

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

| Variable | Required | Default | Description |
|---|---|---|---|
| `AI_PROVIDER` | No | `none` | AI backend: `anthropic`, `openai`, or `none` |
| `AI_API_KEY` | No | — | API key for the configured provider |
| `APP_PORT` | No | `8000` | Port the app listens on inside the container |
| `ALLOWED_ORIGINS` | No | `*` | CORS allowed origins (comma-separated, or `*`) |
| `ALLOWED_SUBNETS` | No | _(all)_ | Restrict access to these CIDRs, e.g. `192.168.1.0/24` |

AI is fully optional — set `AI_PROVIDER=none` or omit `AI_API_KEY` to disable it. The UI will tell you clearly if AI isn't configured.

`ALLOWED_SUBNETS` is useful for locking the app to your LAN. The middleware checks `X-Real-IP` (set by Traefik), then `X-Forwarded-For`, then the raw socket address.

### Example `.env`

```env
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...
ALLOWED_ORIGINS=*
# ALLOWED_SUBNETS=192.168.1.0/24
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

---

## Tags

| Tag | Description |
|---|---|
| `latest` | Most recent build from `main` |
| `YYYYMMDD` | Date-stamped build |
| `monthly` | Automated monthly rebuild (picks up base image security patches) |

---

## Source

[github.com/brandonfhall/whats-for-dinner](https://github.com/brandonfhall/whats-for-dinner)
