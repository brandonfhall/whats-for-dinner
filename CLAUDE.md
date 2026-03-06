# AI Coding Assistant Guide

Project-level instructions for AI coding assistants working on this codebase.

## Project Summary

Household meal planning webapp. Python/FastAPI backend, Alpine.js frontend, SQLite database, Docker deployment. See `docs/ARCHITECTURE.md` for full architecture reference.

## Development Environment

- **Python**: 3.12 (use `.venv/bin/python` for all commands)
- **Virtual environment**: `.venv/` in project root
- **Run tests**: `.venv/bin/python -m pytest tests/ -v`
- **Run server locally**: `.venv/bin/python -m uvicorn app.main:app --reload`
- **Install deps**: `.venv/bin/pip install -r requirements.txt`
- **Test deps**: `.venv/bin/pip install -r requirements-test.txt`

## Code Style & Conventions

### Backend (Python)
- FastAPI with synchronous endpoints (no async DB queries)
- SQLAlchemy 2.0 ORM with `Mapped[]` type annotations
- Pydantic v2 schemas with `model_config = {"from_attributes": True}`
- Routers in `app/routers/` with prefix `/api/<resource>`
- Logging via `logging.getLogger(__name__)` — logger name pattern: `dinner.app`, `dinner.access`
- No Alembic — migrations are manual column additions in `app/database.py:_run_migrations()` using `PRAGMA table_info` checks
- Enums as `(str, enum.Enum)` subclasses stored as text in SQLite
- Soft deletes for meals (set `active=False`, never truly delete)

### Frontend (JavaScript)
- Alpine.js — single `app()` function in `static/app.js`
- Tailwind CSS v4 — compiled at Docker build time, CDN-free
- No build step in development (Tailwind CSS must be rebuilt in Docker)
- Tab-based SPA navigation (no URL routing)
- All API calls through the `api(method, path, body)` helper

### Naming Conventions
- Python: snake_case for functions, variables, file names
- JavaScript: camelCase for methods and variables
- API paths: `/api/<resource>` with kebab-case for multi-word paths (e.g., `/frozen-quantity`)
- Database columns: snake_case

## Testing

### Running Tests
```bash
# Always use the virtual environment
.venv/bin/python -m pytest tests/ -v

# Run a specific test file
.venv/bin/python -m pytest tests/test_meals.py -v

# Run with coverage
.venv/bin/python -m pytest tests/ --cov=app --cov-report=term
```

### Test Structure
- `tests/conftest.py` — shared fixtures, fresh in-memory SQLite per test
- `tests/test_meals.py` — meal library CRUD
- `tests/test_plans.py` — weekly plans, day updates, carry-forward, shopping list
- `tests/test_ai.py` — AI status, prompt building, mocked generation
- `tests/test_inventory.py` — protein inventory CRUD
- `tests/test_settings.py` — settings key-value store
- `tests/test_security.py` — middleware (CORS, subnet, access log)
- `tests/test_frontend_assets.py` — CSS/JS config verification

### Test Patterns
- Use the `client` fixture for API testing (FastAPI TestClient)
- Use the `meals` fixture for tests that need pre-seeded meal data
- AI tests mock `_call_anthropic` / `_call_openai` — never make real API calls
- `MEAL_DEFAULTS` dict provides default field values for creating test meals
- Every test gets a fresh database — no test isolation concerns

### What to Test
- All new API endpoints (happy path + error cases: 404, 409, 422)
- Schema validation (default values, optional fields)
- Business logic (quantity floors at 0, soft deletes, carry-forward)
- AI prompt content for new modes

## Project Constraints

- **No authentication** — internal network only, optional subnet restriction via `ALLOWED_SUBNETS`
- **Dinners only** — the app plans dinner meals, not breakfast/lunch
- **Two people** — household of two, no multi-user features needed
- **SQLite only** — no plans to move to PostgreSQL
- **No build step in dev** — Tailwind is compiled at Docker build time only
- **Offline-capable** — all JS/CSS vendored into the Docker image
- **AI is optional** — app works fully without any AI provider configured

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, middleware, router registration |
| `app/models.py` | SQLAlchemy ORM models |
| `app/schemas.py` | Pydantic request/response schemas |
| `app/database.py` | DB engine, sessions, migrations, seed data |
| `app/routers/meals.py` | Meal CRUD + frozen quantity adjustment |
| `app/routers/plans.py` | Plan CRUD + day updates + shopping list |
| `app/routers/ai.py` | AI plan generation (Claude/OpenAI) |
| `app/routers/settings.py` | Key-value settings store |
| `app/routers/inventory.py` | Protein inventory CRUD |
| `static/app.js` | All frontend Alpine.js logic |
| `static/index.html` | SPA HTML template |

## Adding New Features

1. **Database changes**: Add columns to `app/models.py`, add migration in `app/database.py:_run_migrations()`, new tables auto-created by `create_all()`
2. **Schemas**: Add Pydantic models in `app/schemas.py`
3. **API**: Add endpoint in existing router or create new router in `app/routers/`, register in `app/main.py`
4. **Frontend**: Add data properties and methods to `app()` in `static/app.js`, add UI in `static/index.html`
5. **Tests**: Add tests following existing patterns, run full suite to verify no regressions
6. **Tailwind classes**: If using new Tailwind classes not already in the HTML, they may need to be added to the safelist in `static/css/input.css`
