# What's For Dinner - Architecture Reference

## Overview

Household meal planning web application for two people. Single-container Docker deployment behind Traefik on a home network. No authentication required.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite
- **Frontend**: Alpine.js + Tailwind CSS v4 (no build step in dev; compiled at Docker build time)
- **AI**: Anthropic Claude (default) or OpenAI, configurable via `AI_PROVIDER` env var
- **Container**: Single Docker image, docker-compose with Traefik labels

## High-Level Architecture

```
+---------------------------+
|       Browser (SPA)       |
|  Alpine.js + Tailwind CSS |
|  static/index.html        |
|  static/app.js            |
+------------+--------------+
             |
             | HTTP (JSON API)
             v
+---------------------------+
|     FastAPI Application   |
|       app/main.py         |
|                           |
|  Middleware:              |
|   - CORS                 |
|   - Subnet restriction   |
|   - Access logging       |
|                           |
|  Routers:                |
|   /api/meals      (CRUD) |
|   /api/plans      (CRUD) |
|   /api/ai         (gen)  |
|   /api/settings   (CRUD) |
|   /api/inventory  (CRUD) |
+------------+--------------+
             |
             v
+---------------------------+
|    SQLite Database        |
|   /app/data/dinner.db     |
|                           |
|  Tables:                  |
|   meals, weekly_plans,    |
|   plan_days, settings,    |
|   protein_inventory       |
+---------------------------+
             ^
             |
+---------------------------+
|   AI Provider (external)  |
|  Claude API / OpenAI API  |
|  Called from /api/ai      |
+---------------------------+
```

## Database Schema

### meals
| Column             | Type    | Default      | Notes                                       |
|--------------------|---------|--------------|---------------------------------------------|
| id                 | INTEGER | PK, auto     |                                             |
| name               | TEXT    | required      |                                             |
| meal_type          | TEXT    | home_cooked   | home_cooked / eat_out / other / frozen      |
| notes              | TEXT    | ""            |                                             |
| recipe_url         | TEXT    | ""            |                                             |
| has_leftovers      | BOOL   | false         |                                             |
| easy_to_make       | BOOL   | false         |                                             |
| shared_ingredients | TEXT    | ""            |                                             |
| protein            | TEXT    | ""            | e.g. "Chicken", "Beef", "Tofu"              |
| cuisine            | TEXT    | ""            | e.g. "Italian", "Mexican"                   |
| frozen_quantity    | INTEGER | 0             | Inventory count for frozen meals            |
| protein_servings   | INTEGER | 1             | How many protein servings this meal needs   |
| active             | BOOL   | true          | Soft-delete flag                            |
| created_at         | DATETIME | UTC now     |                                             |

### weekly_plans
| Column       | Type    | Default | Notes                              |
|--------------|---------|---------|------------------------------------|
| id           | INTEGER | PK      |                                    |
| week_start   | DATE    | unique  | Must be a Sunday                   |
| status       | TEXT    | draft   | draft / active / complete          |
| ai_generated | BOOL   | false   |                                    |
| notes        | TEXT    | ""      |                                    |
| created_at   | DATETIME | UTC now |                                   |

### plan_days
| Column        | Type    | Default | Notes                            |
|---------------|---------|---------|----------------------------------|
| id            | INTEGER | PK      |                                  |
| plan_id       | INTEGER | FK      | -> weekly_plans.id               |
| day_of_week   | INTEGER | required | 0=Sun, 1=Mon, ..., 6=Sat       |
| day_type      | TEXT    | skip    | home_cooked / eat_out / skip     |
| meal_id       | INTEGER | nullable | -> meals.id (for home_cooked)   |
| custom_name   | TEXT    | ""      | Restaurant name for eat_out      |
| notes         | TEXT    | ""      |                                  |
| carry_forward | BOOL   | false   | Copy to next week if unplanned   |

### protein_inventory
| Column        | Type    | Default    | Notes                              |
|---------------|---------|------------|------------------------------------|
| id            | INTEGER | PK         |                                    |
| protein_name  | TEXT    | unique     | Key like "Chicken", "Beef"         |
| display_name  | TEXT    | required   | Display label                      |
| emoji         | TEXT    | ""         | Emoji for UI display               |
| group         | TEXT    | "meat"     | "meat" or "veg" for color coding   |
| quantity      | FLOAT   | 0          | Current stock in standard servings |
| unit          | TEXT    | "servings" | Unit label                         |

### settings
| Column | Type | Notes                                    |
|--------|------|------------------------------------------|
| key    | TEXT | PK (gym_days, eat_out_days, ai_provider) |
| value  | TEXT | JSON-encoded                             |

## API Endpoints

### Meals (`/api/meals`)
| Method | Path                              | Description                   |
|--------|-----------------------------------|-------------------------------|
| GET    | /                                 | List meals (active_only)      |
| POST   | /                                 | Create meal                   |
| GET    | /{meal_id}                        | Get meal by ID                |
| PUT    | /{meal_id}                        | Update meal                   |
| DELETE | /{meal_id}                        | Soft-delete meal              |
| PATCH  | /{meal_id}/frozen-quantity?delta=N | Adjust frozen inventory count |

### Plans (`/api/plans`)
| Method | Path                         | Description                    |
|--------|------------------------------|--------------------------------|
| GET    | /                            | List all plans (summary)       |
| GET    | /current                     | Get/create current week plan   |
| GET    | /week/{week_start}           | Get/create plan for week       |
| POST   | /                            | Create plan                    |
| GET    | /{plan_id}                   | Get plan with days             |
| PUT    | /{plan_id}/days/{dow}        | Update a day in a plan         |
| PUT    | /{plan_id}/notes             | Update plan notes              |
| PUT    | /{plan_id}/status            | Update plan status             |
| DELETE | /{plan_id}                   | Delete plan (cascade days)     |
| GET    | /{plan_id}/shopping-list     | Generate shopping list         |

### AI (`/api/ai`)
| Method | Path      | Description                     |
|--------|-----------|---------------------------------|
| GET    | /status   | Check AI configuration status   |
| POST   | /generate | Generate meal plan suggestions  |

### Inventory (`/api/inventory`)
| Method | Path                                    | Description                |
|--------|-----------------------------------------|----------------------------|
| GET    | /proteins                               | List all protein entries   |
| POST   | /proteins                               | Add new protein            |
| PUT    | /proteins/{protein_name}                | Update protein entry       |
| PATCH  | /proteins/{protein_name}/adjust?delta=N | Adjust quantity by delta   |
| DELETE | /proteins/{protein_name}                | Remove protein entry       |

### Backup (`/api/backup`)
| Method | Path                 | Description                          |
|--------|----------------------|--------------------------------------|
| POST   | /                    | Create backup and download            |
| GET    | /list                | List available backup files           |
| GET    | /download/{filename} | Download a specific backup            |

### Settings (`/api/settings`)
| Method | Path | Description       |
|--------|------|-------------------|
| GET    | /    | Read all settings |
| PUT    | /    | Update settings   |

## Features

1. **Meal Library**: CRUD for meals with type (home_cooked, eat_out, other, frozen), protein, cuisine, tags (easy, leftovers), recipe URLs
2. **Frozen Meal Inventory**: Track frozen meal prep portions with +/- quantity controls in library and editor
3. **Protein Inventory**: Database-driven protein categories (seeded with 14 defaults) with stock tracking per protein type
4. **Weekly Planning**: 7-day grid (Sun-Sat), day editor with meal picker (includes frozen meals), carry-forward
5. **AI Suggestions**: Three modes:
   - "Mix it up" - favor less-used meals
   - "Play it safe" - favor favorites
   - "On hand" - only suggest meals with available protein/frozen stock
6. **Shopping List**: Read-only list comparing plan needs vs inventory (protein stock + frozen meal count)
7. **Month View**: Calendar overview, click to navigate to any week
8. **Settings**: Gym days, eat-out days, AI provider selection

## Frontend Structure

- Single-page application with tab-based navigation (no URL routing)
- Tabs: This Week, Meal Library, Inventory, Month View, Settings
- Slide-in panel for day editing
- Modal for meal create/edit
- All state managed in one Alpine.js `app()` function
- Protein categories loaded from API (not hardcoded)

## Key Design Patterns

- Soft deletes for meals (active=false)
- Carry-forward copies meals from previous week
- Settings stored as JSON key-value pairs
- Migrations via PRAGMA table_info checks (no Alembic)
- Real IP detection for Traefik (X-Real-IP, X-Forwarded-For)
- Frozen meals use `meal_type=frozen` with `frozen_quantity` on the meal itself
- Frozen meals have no protein selection or protein servings (they're self-contained)
- Protein inventory is a separate global table shared across all meals
- Shopping list computed on-the-fly (not persisted)
- Protein seed data auto-populated on first startup if table is empty
- Non-negative quantities enforced at both code layer (`max(0, ...)`) and DB layer (`CHECK` constraints) for `frozen_quantity`, `protein_servings`, and `protein_inventory.quantity`
- Automatic database backup before migrations (SQLite backup API); manual backup via `/api/backup`
- Weekly backup on startup (one per calendar week, skips if already exists)
- Backup files stored in `data/backups/`, pruned to last 5 per reason (pre_migration, weekly, manual are independent pools)
