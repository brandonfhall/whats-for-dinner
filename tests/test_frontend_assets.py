"""Tests that verify the frontend asset configuration is correct.

These are static-analysis tests — no build step is required.  They guard
against accidental re-introduction of CDN dependencies, removal of
dynamic-class safelist entries from static/css/input.css, and regression
of mobile layout fixes.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


# ── index.html CDN / local-path checks ───────────────────────────────────────

def test_index_html_no_tailwind_cdn():
    """index.html must not reference the Tailwind Play CDN."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" not in html


def test_index_html_no_alpine_cdn():
    """index.html must not load Alpine.js from an external CDN."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "jsdelivr.net" not in html
    assert "unpkg.com" not in html


def test_index_html_links_local_tailwind_css():
    """index.html references the locally compiled Tailwind CSS file."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "/static/css/tailwind.css" in html


def test_index_html_links_local_alpine():
    """index.html loads Alpine.js from the vendored path."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "/static/vendor/alpine.min.js" in html


def test_accessibility_attributes_exist():
    """Key UI elements must have aria-labels for accessibility."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    # aria-labels for icon-only buttons
    assert 'aria-label="Previous week"' in html
    assert 'aria-label="Next week"' in html
    assert 'aria-label="Clear all days this week"' in html
    assert 'aria-label="Edit meal"' in html
    assert 'aria-label="Edit protein"' in html
    assert 'aria-label="Remove protein"' in html
    assert 'aria-label="Previous month"' in html
    assert 'aria-label="Next month"' in html
    assert 'aria-label="Close"' in html

    # aria roles for modals
    assert 'role="dialog" aria-modal="true" aria-label="Day editor"' in html
    assert 'role="dialog" aria-modal="true" aria-label="Confirm clear week"' in html
    assert 'role="dialog" aria-modal="true" aria-label="Meal editor"' in html
    assert 'role="dialog" aria-modal="true" aria-label="Confirm AI plan generation"' in html


# ── input.css safelist ────────────────────────────────────────────────────────

# ── Mobile layout regression tests ───────────────────────────────────────────

def test_nav_logo_collapses_on_mobile():
    """The nav logo must use responsive spans so it collapses on small screens.

    Without this the logo + 5 tabs overflow on 375px phones.
    """
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    # The logo area must hide full text on mobile and show only short form
    assert 'sm:hidden' in html, "Nav logo must have a sm:hidden short form for mobile"
    assert 'hidden sm:inline' in html, "Nav logo must have a hidden sm:inline full form for desktop"


def test_nav_settings_tab_short_label_is_compact():
    """The Settings tab short label must be compact (emoji or ≤5 chars).

    'Settings' as a short label overflows the nav bar on narrow phones.
    """
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    # Find the settings tab definition and extract its short value
    match = re.search(r"id:\s*'settings'.*?short:\s*['\"](.+?)['\"]", js)
    assert match, "Could not find settings tab short label in app.js"
    short = match.group(1)
    # Allow single emoji (len > 1 due to surrogate pairs is fine) or ≤5 ASCII chars
    is_emoji_only = len(short.encode('utf-8')) > len(short)  # multi-byte = emoji
    assert is_emoji_only or len(short) <= 5, (
        f"Settings short label '{short}' is too long for mobile nav — "
        "use an emoji or ≤5 characters"
    )


def test_meal_type_buttons_use_responsive_grid():
    """The meal editor type selector must use a 2-col mobile grid, not a single flex row.

    Four flex-1 buttons in a row leave 'Home cooked' with only ~70px on mobile,
    too narrow to display legibly.
    """
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert 'grid-cols-2' in html, (
        "Meal editor type buttons must use grid-cols-2 for mobile layout. "
        "A plain flex row overflows on narrow screens."
    )


def test_shopping_list_rows_stack_on_mobile():
    """Shopping list item rows must stack vertically on mobile.

    A single flex justify-between row with badge + name + need/have/buy
    overflows on narrow phone screens.
    """
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert 'flex-col sm:flex-row' in html, (
        "Shopping list rows must use flex-col sm:flex-row to stack on mobile. "
        "A plain flex justify-between row overflows on narrow screens."
    )


def test_filter_buttons_wrap_on_mobile():
    """Meal library filter pill buttons must be allowed to wrap on mobile."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    # The filter container should have flex-wrap (or flex flex-wrap or flex-wrap alone)
    assert 'flex-wrap' in html, (
        "Meal library filter buttons must use flex-wrap so they wrap on narrow screens."
    )


def test_day_cards_show_date_alongside_name():
    """Weekly view day cards must display the date alongside the day name.

    The day header uses dayDateStr() to calculate M/D from the plan's
    week_start + day_of_week so users see 'SUNDAY - 3/22' rather than
    just 'SUNDAY'.
    """
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert 'dayDateStr(' in html, (
        "Weekly day cards must call dayDateStr() to show the date next to "
        "the day name."
    )
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'dayDateStr(' in js, (
        "app.js must define a dayDateStr() function to compute the date "
        "for each day of the week."
    )


def test_month_view_shows_other_days_with_custom_text():
    """Month view must display 'Other' days that have custom text.

    Days with day_type='skip' and a custom_name (e.g. 'Leftovers')
    should still show their label on the month calendar rather than
    being hidden entirely.
    """
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    # The month view x-show condition must allow skip days with custom_name
    assert ".custom_name)" in html, (
        "Month view must check custom_name so 'Other' days with text "
        "are visible on the calendar."
    )


def test_input_css_safelists_dynamic_classes():
    """input.css must force-include every class built from template literals.

    index.html constructs class names like `bg-${opt.c}-600` at runtime.
    The Tailwind scanner cannot detect these statically, so they must appear
    in an @source inline() directive or they will be purged from the compiled CSS.
    """
    config = (ROOT / "static" / "css" / "input.css").read_text(encoding="utf-8")
    required = [
        "bg-green-600", "border-green-600",
        "bg-blue-600",  "border-blue-600",
        "bg-gray-600",  "border-gray-600",
    ]
    missing = [cls for cls in required if cls not in config]
    assert not missing, f"Missing @source inline entries in static/css/input.css: {missing}"
