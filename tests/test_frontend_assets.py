"""Tests that verify the frontend asset configuration is correct.

These are static-analysis tests — no build step is required.  They guard
against accidental re-introduction of CDN dependencies or removal of
dynamic-class safelist entries from tailwind.config.js.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent


# ── index.html CDN / local-path checks ───────────────────────────────────────

def test_index_html_no_tailwind_cdn():
    """index.html must not reference the Tailwind Play CDN."""
    html = (ROOT / "static" / "index.html").read_text()
    assert "cdn.tailwindcss.com" not in html


def test_index_html_no_alpine_cdn():
    """index.html must not load Alpine.js from an external CDN."""
    html = (ROOT / "static" / "index.html").read_text()
    assert "jsdelivr.net" not in html
    assert "unpkg.com" not in html


def test_index_html_links_local_tailwind_css():
    """index.html references the locally compiled Tailwind CSS file."""
    html = (ROOT / "static" / "index.html").read_text()
    assert "/static/css/tailwind.css" in html


def test_index_html_links_local_alpine():
    """index.html loads Alpine.js from the vendored path."""
    html = (ROOT / "static" / "index.html").read_text()
    assert "/static/vendor/alpine.min.js" in html


# ── tailwind.config.js safelist ───────────────────────────────────────────────

def test_tailwind_config_safelists_dynamic_classes():
    """tailwind.config.js safelists every class built from template literals.

    index.html constructs class names like `bg-${opt.c}-600` at runtime.
    The Tailwind scanner cannot detect these statically, so they must appear
    in the safelist or they will be purged from the compiled CSS.
    """
    config = (ROOT / "tailwind.config.js").read_text()
    required = [
        "bg-green-600", "border-green-600",
        "bg-blue-600",  "border-blue-600",
        "bg-gray-600",  "border-gray-600",
    ]
    missing = [cls for cls in required if cls not in config]
    assert not missing, f"Missing safelist entries in tailwind.config.js: {missing}"
