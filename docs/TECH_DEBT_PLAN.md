# Code Review & Tech Debt Implementation Plan

**Author:** Opus 4.6 (Senior Engineer Review)
**Date:** 2026-03-29
**Status:** Ready for implementation (Sonnet)

## Context

Senior code review of the "What's for Dinner" app revealed opportunities across 8 work units: infrastructure hardening, backend code deduplication, validation improvements, test maintainability, frontend quality, CI strictness, CSS completeness, and documentation. The codebase is well-structured (~990 LOC backend, ~630 LOC frontend, 193 tests at 93% coverage) but has accumulated tech debt in duplicated patterns, hardcoded config, missing Docker best practices, and accessibility gaps.

---

## PR 1: Docker Hardening

**Branch:** `refactor/docker-hardening` from `develop`

### 1a. Create `.dockerignore` (new file, project root)
```
.git
.github
.venv
.vscode
.pytest_cache
.coverage
htmlcov
__pycache__
*.pyc
*.pyo
.env
.env.example
.DS_Store
.claude
docs/
tests/
data/
node_modules/
CLAUDE.md
README.md
DOCKERHUB.md
pytest.ini
requirements-test.txt
docker-compose*.yml
```

### 1b. Generate `package-lock.json`
Run `npm install` locally, commit the resulting `package-lock.json`. Then in `Dockerfile`:
- Change `COPY package.json ./` to `COPY package.json package-lock.json ./`
- Change `RUN npm install` to `RUN npm ci`

### 1c. Non-root user in `Dockerfile`
After `RUN mkdir -p /app/data`, add:
```dockerfile
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app /app/data
USER appuser
```

### 1d. Add `HEALTHCHECK` to `Dockerfile`
Before `CMD`:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/plans')"]
```

### Verification
- `docker build . -t test:latest` succeeds
- Container starts, healthcheck passes
- No pytest changes needed

---

## PR 2: Extract Shared Utilities (`app/utils.py`)

**Branch:** `refactor/extract-shared-utils` from `develop`

### 2a. Create `app/utils.py`
```python
"""Shared helpers used across multiple routers."""
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session

DAY_NAMES = [
    "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday",
]

def get_or_404(db: Session, model, detail: str = "Not found", **filters):
    """Query for a single row by the given filters; raise 404 if missing."""
    q = db.query(model)
    for attr, value in filters.items():
        q = q.filter(getattr(model, attr) == value)
    obj = q.first()
    if not obj:
        raise HTTPException(status_code=404, detail=detail)
    return obj

def sunday_of(d: date) -> date:
    """Return the Sunday that starts the week containing *d*."""
    return d - timedelta(days=(d.weekday() + 1) % 7)
```

### 2b. Update `app/routers/plans.py`
- **Delete** `DAY_NAMES` (line 17) and `_sunday_of` function (lines 20-22)
- **Add import:** `from app.utils import DAY_NAMES, sunday_of, get_or_404`
- **Replace** all `_sunday_of(` calls with `sunday_of(`
- **Replace** the ~5 instances of `db.query(WeeklyPlan).filter(...).first(); if not: raise 404` with `get_or_404(db, WeeklyPlan, detail="Plan not found", id=plan_id)`
- **Keep** `_build_plan_days` and `_load_plan` in plans.py (they use plan-specific models like `PlanDay`, `DayType`, `joinedload`)

### 2c. Update `app/routers/meals.py`
- **Add import:** `from app.utils import get_or_404`
- **Replace** the ~4 instances of the query-then-404 pattern with `get_or_404(db, Meal, detail="Meal not found", id=meal_id)`
- Note: the `active=True` filter in some queries means you'll need either a separate `get_or_404` call with `active=True` as a filter, or keep the manual query for those specific cases

### 2d. Update `app/routers/inventory.py`
- **Add import:** `from app.utils import get_or_404`
- **Replace** the ~3 instances with `get_or_404(db, ProteinInventory, detail="Protein not found", protein_name=protein_name)`

### 2e. Update `app/routers/ai.py`
- **Delete** `DAY_NAMES` (line 19)
- **Replace** the deferred import at line 367:
  ```python
  # OLD (inside function body):
  from app.routers.plans import _sunday_of, _build_plan_days, _load_plan

  # NEW (at top of file):
  from app.utils import DAY_NAMES, sunday_of
  from app.routers.plans import _build_plan_days, _load_plan
  ```
  This is safe — no circular import. The chain is linear: `ai -> plans -> settings`.
- **Replace** `_sunday_of(` with `sunday_of(`

### 2f. Create `tests/test_utils.py` (new file)
```python
from datetime import date
import pytest
from fastapi import HTTPException
from app.utils import DAY_NAMES, sunday_of, get_or_404
from app.models import Meal

def test_get_or_404_returns_object(db_session):
    """Create a meal via the ORM, then verify get_or_404 finds it."""
    # Use the db session from conftest to add a Meal directly
    # Then call get_or_404(db, Meal, id=meal.id)

def test_get_or_404_raises_404(db_session):
    """Verify get_or_404 raises HTTPException 404 for missing records."""
    with pytest.raises(HTTPException) as exc_info:
        get_or_404(db_session, Meal, detail="Meal not found", id=99999)
    assert exc_info.value.status_code == 404

def test_sunday_of():
    # Wednesday 2026-04-01 -> Sunday 2026-03-29
    assert sunday_of(date(2026, 4, 1)) == date(2026, 3, 29)
    # Sunday itself -> same Sunday
    assert sunday_of(date(2026, 3, 29)) == date(2026, 3, 29)
    # Saturday 2026-04-04 -> Sunday 2026-03-29
    assert sunday_of(date(2026, 4, 4)) == date(2026, 3, 29)

def test_day_names():
    assert len(DAY_NAMES) == 7
    assert DAY_NAMES[0] == "Sunday"
    assert DAY_NAMES[6] == "Saturday"
```

Note: You may need to add a `db_session` fixture to conftest.py that provides a raw SQLAlchemy Session (the existing `client` fixture uses TestClient). Alternatively, write these as API-level tests using the `client` fixture.

### Verification
All 193+ existing tests pass unchanged + new test_utils.py tests pass.

---

## PR 3: Backend Quality Fixes (Validation, Config, Error Handling)

**Branch:** `refactor/backend-quality-fixes` from `develop`

### 3a. Pydantic `Field(ge=0)` validators in `app/schemas.py`

**Add import** (line 3): `from pydantic import BaseModel, Field`

**In `MealBase` (line 10-area):**
- `frozen_quantity: int = 0` -> `frozen_quantity: int = Field(default=0, ge=0)`
- `protein_servings: int = 1` -> `protein_servings: int = Field(default=1, ge=0)`

**In `MealUpdate` (line 28-area):**
- `frozen_quantity: Optional[int] = None` -> `frozen_quantity: Optional[int] = Field(default=None, ge=0)`
- `protein_servings: Optional[int] = None` -> `protein_servings: Optional[int] = Field(default=None, ge=0)`

**In `ProteinInventoryCreate` (around line 141):**
- `quantity: float = 0` -> `quantity: float = Field(default=0, ge=0)`

**In `ProteinInventoryUpdate` (around line 150):**
- `quantity: Optional[float] = None` -> `quantity: Optional[float] = Field(default=None, ge=0)`

**Then remove `max(0, ...)` clamping from routers:**
- `app/routers/meals.py` create endpoint (~line 45-46): Remove `data["frozen_quantity"] = max(0, ...)` and `data["protein_servings"] = max(0, ...)`
- `app/routers/meals.py` update endpoint (~line 70-71): Remove the `if field in ("frozen_quantity", "protein_servings"): value = max(0, value)` block
- `app/routers/inventory.py` create endpoint (~line 33): Remove `data["quantity"] = max(0, ...)`
- `app/routers/inventory.py` update endpoint (~lines 56-57): Remove the `if field == "quantity": value = max(0, value)` block

**IMPORTANT: KEEP** `max(0, ...)` in:
- `adjust_frozen_quantity` endpoint in meals.py (computes `meal.frozen_quantity + delta`)
- `adjust_protein` endpoint in inventory.py (computes `entry.quantity + delta`)
These operate on computed values, not schema input.

### 3b. Configurable AI model names in `app/routers/ai.py`

**In `_call_anthropic` (line 229):**
```python
# OLD:
model="claude-sonnet-4-6",
# NEW:
model=os.getenv("AI_MODEL_ANTHROPIC", "claude-sonnet-4-6"),
```

**In `_call_openai` (line 245):**
```python
# OLD:
model="gpt-4o",
# NEW:
model=os.getenv("AI_MODEL_OPENAI", "gpt-4o"),
```

### 3c. Add timeout to AI API calls in `app/routers/ai.py`

**In `_call_anthropic` (line 227):**
```python
# OLD:
client = anthropic.Anthropic(api_key=key)
# NEW:
timeout = float(os.getenv("AI_TIMEOUT", "60"))
client = anthropic.Anthropic(api_key=key, timeout=timeout)
```

**In `_call_openai` (line 243):**
```python
# OLD:
client = OpenAI(api_key=key)
# NEW:
timeout = float(os.getenv("AI_TIMEOUT", "60"))
client = OpenAI(api_key=key, timeout=timeout)
```

### 3d. Fix backup resource handling in `app/database.py` (lines 49-55)

```python
# OLD:
src_conn = sqlite3.connect(src)
dst_conn = sqlite3.connect(dest)
try:
    src_conn.backup(dst_conn)
finally:
    dst_conn.close()
    src_conn.close()

# NEW:
with sqlite3.connect(src) as src_conn, sqlite3.connect(dest) as dst_conn:
    src_conn.backup(dst_conn)
```

### 3e. Error handling consistency in `app/routers/ai.py`

**Line 348 — change 400 to 503:**
```python
# OLD:
raise HTTPException(status_code=400, detail="AI is disabled (AI_PROVIDER=none).")
# NEW:
raise HTTPException(status_code=503, detail="AI is disabled (AI_PROVIDER=none).")
```

**Lines 361-363 — split broad exception:**
```python
# OLD:
except Exception as exc:
    logger.error("AI generate failed | provider=%s error=%s", provider, exc)
    raise HTTPException(status_code=500, detail=f"AI request failed: {exc}") from exc

# NEW:
except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
    logger.error("AI generate failed | provider=%s error=%s", provider, exc)
    raise HTTPException(status_code=500, detail=f"AI request failed: {exc}") from exc
except Exception as exc:
    logger.error("AI generate failed | provider=%s error=%s", provider, exc)
    raise HTTPException(status_code=502, detail=f"AI provider error: {exc}") from exc
```

### 3f. JSON error handling in `app/routers/settings.py` (line 26)

```python
# OLD:
result[row.key] = json.loads(row.value)

# NEW:
try:
    result[row.key] = json.loads(row.value)
except (json.JSONDecodeError, TypeError):
    pass  # skip corrupt values, keep Pydantic defaults
```

### 3g. Update `.env.example`

Add after the `AI_API_KEY` line:
```env
# Override AI model names (defaults shown)
# AI_MODEL_ANTHROPIC=claude-sonnet-4-6
# AI_MODEL_OPENAI=gpt-4o
# AI_TIMEOUT=60
```

### Test Updates Required
- **Negative value tests** (6 tests in test_meals.py, 2 in test_inventory.py): Change assertions from "value floors to 0" to `assert r.status_code == 422` (Pydantic now rejects negatives at the schema level)
- **AI disabled test**: Change `assert r.status_code == 400` to `assert r.status_code == 503`
- **New test**: Corrupt settings JSON — write a bad value directly to the DB via ORM, assert `GET /api/settings` still returns defaults
- **New test**: AI model env var override — mock the Anthropic/OpenAI client constructor, patch `AI_MODEL_ANTHROPIC` env var, verify the model kwarg

---

## PR 4: Test Fixture Improvements

**Branch:** `refactor/test-fixtures` from `develop`

### 4a. Add factory fixtures to `tests/conftest.py`

```python
@pytest.fixture()
def create_meal_factory(client):
    """Return a factory function that creates a meal via the API."""
    def _create(name="Test Pasta", **kwargs):
        payload = {**MEAL_DEFAULTS, "name": name, "meal_type": "home_cooked", **kwargs}
        r = client.post("/api/meals", json=payload)
        assert r.status_code == 201, r.text
        return r.json()
    return _create


@pytest.fixture()
def create_protein_factory(client):
    """Return a factory function that creates a protein via the API."""
    def _create(name="TestProtein", display_name=None, **kwargs):
        payload = {"protein_name": name, "display_name": display_name or name, **kwargs}
        r = client.post("/api/inventory/proteins", json=payload)
        assert r.status_code == 201, r.text
        return r.json()
    return _create


@pytest.fixture()
def ai_env():
    """Patch environment for AI-enabled tests."""
    from unittest.mock import patch
    return patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-test"})
```

### 4b. Refactor tests to use factories
- **`test_inventory.py`**: Replace inline `client.post("/api/inventory/proteins", ...)` calls with `create_protein_factory`
- **`test_meals.py`**: Replace the local `create_meal()` helper function with `create_meal_factory` fixture usage
- **`test_ai.py`**: Replace repeated `patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-test"})` with `ai_env` fixture

### Verification
All tests pass with identical behavior. This is a pure refactor of test code.

---

## PR 5: Frontend Error Handling & Accessibility

**Branch:** `refactor/frontend-quality` from `develop`

### 5a. Add `handleError()` method to `static/app.js`

Add after the `api()` method (~line 107):
```javascript
handleError(msg, e) {
  alert(msg + ': ' + e.message);
},
```

Then replace all 10 instances of `alert('Failed to X: ' + e.message)` with `this.handleError('Failed to X', e)`. The affected lines are approximately: 368, 398, 412, 531, 546, 560, 576, 586, 597, 624.

This gives a single point to later upgrade from `alert()` to toast notifications.

### 5b. Accessibility improvements in `static/index.html`

**Add `aria-label` to all icon-only buttons:**
- Prev week `<button>`: add `aria-label="Previous week"`
- Next week `<button>`: add `aria-label="Next week"`
- Clear week `<button>`: add `aria-label="Clear all days this week"`
- Edit meal pencil `<button>`: add `aria-label="Edit meal"`
- Edit protein `<button>`: add `aria-label="Edit protein"`
- Delete protein `<button>`: add `aria-label="Remove protein"`
- Prev month `<button>`: add `aria-label="Previous month"`
- Next month `<button>`: add `aria-label="Next month"`
- Close day editor `<button>`: add `aria-label="Close"`
- Close meal editor `<button>`: add `aria-label="Close"`

**Add dialog roles to modals:**
- Day editor panel: add `role="dialog" aria-modal="true" aria-label="Day editor"`
- Clear week confirm modal: add `role="dialog" aria-modal="true" aria-label="Confirm clear week"`
- Meal editor modal: add `role="dialog" aria-modal="true" aria-label="Meal editor"`

### Verification
- Update `tests/test_frontend_assets.py` to assert `aria-label` attributes exist on key buttons
- Verify `role="dialog"` appears on all three modals
- All backend tests pass unchanged

---

## PR 6: CI Linting & Config Consolidation

**Branch:** `refactor/ci-lint-config` from `develop`

### 6a. Add flake8 to `.github/workflows/test.yml`

After the "Install dependencies" step, add:
```yaml
      - name: Lint with flake8
        run: |
          pip install flake8
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
          flake8 . --count --max-complexity=10 --max-line-length=127 --statistics
```

Note: No `--exit-zero` — lint failures should block PRs.

### 6b. Remove `--exit-zero` from `.github/workflows/docker-publish.yml`

Line 39, change:
```yaml
          flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```
to:
```yaml
          flake8 . --count --max-complexity=10 --max-line-length=127 --statistics
```

### 6c. Create `.flake8` config file (project root)

```ini
[flake8]
max-line-length = 127
max-complexity = 10
exclude = .venv,node_modules,__pycache__,.git
```

### 6d. Migrate pytest config to `pyproject.toml`

Create `pyproject.toml` (project root):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=90"
```

Then **delete** `pytest.ini` since `pyproject.toml` replaces it.

### Verification
Run `flake8` locally first — fix any violations found in this same PR before committing.

---

## PR 7: Tailwind CSS Safelist Completeness

**Branch:** `refactor/tailwind-safelist` from `develop`

### 7a. Audit and update safelist in `static/css/input.css`

Current safelist (line 16) covers `bg-{green,blue,gray,orange}-600` and `border-{green,blue,gray,orange}-600`.

Audit `index.html` for any dynamic classes using template literals (look for backtick strings with `${...}`) that aren't covered. Add any missing classes to the `@source inline(...)` directive.

### 7b. Update CI CSS class verification

In `.github/workflows/test.yml` and `docker-publish.yml`, ensure the CSS class verification loop includes `bg-orange-600` and `border-orange-600` if not already present in the check list.

### Verification
Run a Docker build, then inspect the generated `static/css/tailwind.css` to confirm all safelisted classes are present.

---

## PR 8: Documentation Updates

**Branch:** `docs/update-docs` from `develop` — **do this last**

### 8a. Update `CLAUDE.md`
- Under "Code Style & Conventions > Backend (Python)": add bullet about `app/utils.py` containing `DAY_NAMES`, `sunday_of()`, and `get_or_404()`
- Under "Testing > Test Patterns": mention factory fixtures (`create_meal_factory`, `create_protein_factory`, `ai_env`)
- Under "Key Files" table: add row for `app/utils.py | Shared helpers (get_or_404, sunday_of, DAY_NAMES)`

### 8b. Update `docs/ARCHITECTURE.md`
Add `app/utils.py` to the file/module descriptions section.

### 8c. Verify `.env.example`
Ensure it documents all new env vars: `AI_MODEL_ANTHROPIC`, `AI_MODEL_OPENAI`, `AI_TIMEOUT`

---

## Execution Order

```
Independent (can parallelize):  PR 1, PR 2, PR 5, PR 7
After PR 2:                     PR 3
After PR 2 + PR 3:              PR 4
After all code PRs:             PR 6
Last:                           PR 8
```

**Sequential order for a single implementer:**
```
PR 1 -> PR 2 -> PR 3 -> PR 5 -> PR 7 -> PR 4 -> PR 6 -> PR 8
```

## What Was Deliberately Excluded

These items were identified in the review but excluded from the plan as over-engineering for a 2-person household app:

- **Async database support** — SQLite with sync is fine at this scale
- **PostgreSQL migration** — overkill for the use case
- **Rate limiting** — internal network only, no auth needed
- **Alpine.js state restructuring** — monolithic state object works fine at ~630 LOC
- **Splitting test_ai.py** — 661 lines is large but manageable
- **Server-side meal filtering** — client-side is fine for <100 meals
- **CSP `unsafe-eval` removal** — Alpine.js requires it, this is expected behavior
