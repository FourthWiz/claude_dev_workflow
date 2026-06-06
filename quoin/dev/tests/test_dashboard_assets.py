"""Tests for quoin/core/scripts/dashboard_assets/ — SPA static files.

T-06: index.html validity, local-only refs, finalized-toggle + phase-legend.
T-07: dashboard.css validity, no remote imports, required selectors.
T-08/T-09: app.js validity, no external refs, EventSource absent (polling-only).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ASSETS_DIR = (
    Path(__file__).resolve().parents[2] / "core" / "scripts" / "dashboard_assets"
)

_INDEX_HTML = _ASSETS_DIR / "index.html"
_CSS = _ASSETS_DIR / "dashboard.css"
_JS = _ASSETS_DIR / "app.js"

_EXTERNAL_URL_RE = re.compile(r'https?://|//[a-zA-Z]|cdn\.|@import\s+url\s*\(https?', re.IGNORECASE)


class TestAssetsExist:
    def test_index_html_exists(self):
        assert _INDEX_HTML.exists(), f"index.html not found at {_INDEX_HTML}"

    def test_dashboard_css_exists(self):
        assert _CSS.exists(), f"dashboard.css not found at {_CSS}"

    def test_app_js_exists(self):
        assert _JS.exists(), f"app.js not found at {_JS}"


class TestNoExternalUrls:
    """No CDN, no external src/href in any asset file."""

    def _check_file(self, path: Path):
        content = path.read_text(encoding="utf-8")
        matches = _EXTERNAL_URL_RE.findall(content)
        assert not matches, (
            f"{path.name} contains external URL(s): {matches[:3]}"
        )

    def test_index_html_no_external(self):
        self._check_file(_INDEX_HTML)

    def test_css_no_external(self):
        self._check_file(_CSS)

    def test_app_js_no_external(self):
        self._check_file(_JS)


class TestIndexHtml:
    """T-06 acceptance criteria for index.html."""

    def test_valid_html5_doctype(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert content.strip().lower().startswith("<!doctype html>")

    def test_references_local_css(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "./dashboard.css" in content or "dashboard.css" in content

    def test_references_local_js(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "./app.js" in content or "app.js" in content

    def test_noscript_fallback_present(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "<noscript" in content.lower()

    def test_finalized_toggle_control(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        # Must have a toggle for finalized tasks (checkbox input)
        assert 'type="checkbox"' in content or "type='checkbox'" in content
        assert "finalized" in content.lower()

    def test_phase_legend_present(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "legend" in content.lower() or "phase" in content.lower()

    def test_implement_indistinguishable_note(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        # Must note the implement/in-progress indistinguishability per D-13
        assert "indistinguishable" in content.lower() or "git probe" in content.lower()


class TestDashboardCss:
    """T-07 acceptance criteria for dashboard.css."""

    def test_no_remote_import(self):
        content = _CSS.read_text(encoding="utf-8")
        # No @import url(http...) or @import with remote url
        assert "@import url(http" not in content
        assert "@import url('http" not in content
        assert '@import url("http' not in content

    def test_task_table_selector(self):
        content = _CSS.read_text(encoding="utf-8")
        assert ".task-table" in content

    def test_detail_pane_selector(self):
        content = _CSS.read_text(encoding="utf-8")
        assert ".detail-pane" in content

    def test_phase_chip_selector(self):
        content = _CSS.read_text(encoding="utf-8")
        assert ".phase-chip" in content

    def test_cost_badge_selector(self):
        content = _CSS.read_text(encoding="utf-8")
        assert ".cost-badge" in content

    def test_non_empty(self):
        content = _CSS.read_text(encoding="utf-8")
        assert len(content.strip()) > 100


class TestAppJs:
    """T-08 + T-09 acceptance criteria for app.js."""

    def test_no_eventsource(self):
        """SSE was cut — app.js must not reference EventSource (D-10)."""
        content = _JS.read_text(encoding="utf-8")
        # EventSource is the browser SSE constructor — absent when polling-only
        assert "new EventSource" not in content
        assert "EventSource(" not in content

    def test_polling_setinterval_present(self):
        """Live refresh via setInterval (~3s) must be present (T-09, D-10)."""
        content = _JS.read_text(encoding="utf-8")
        assert "setInterval" in content

    def test_model_or_effort_used_not_model(self):
        """SPA reads model_or_effort from rows, NOT bare 'model' key (T-08)."""
        content = _JS.read_text(encoding="utf-8")
        assert "model_or_effort" in content
        # Must not read row['model'] as the key (row.model_or_effort is allowed;
        # it contains row.model as a substring but that is the correct field name)
        assert "row['model']" not in content
        # No standalone .model property access (only .model_or_effort is valid)
        import re
        standalone = re.search(r'row\.model\b(?!_or_effort)', content)
        assert standalone is None, (
            "app.js uses row.model without _or_effort suffix; "
            "the correct key is model_or_effort"
        )

    def test_badge_text_function_handles_modes(self):
        """app.js must handle usd/tokens/counts modes for cost badge (T-08)."""
        content = _JS.read_text(encoding="utf-8")
        assert "usd" in content
        assert "tokens" in content
        assert "counts" in content or "cost unavailable" in content

    def test_by_phase_branches_on_mode(self):
        """Detail pane branches on cost.mode for by_phase rendering (T-09, D-14)."""
        content = _JS.read_text(encoding="utf-8")
        # Must branch on cost.mode
        assert "cost.mode" in content or "mode === 'usd'" in content or 'mode === "usd"' in content

    def test_api_tasks_url_helper(self):
        """tasksUrl function or equivalent must build the correct URL (T-08)."""
        content = _JS.read_text(encoding="utf-8")
        assert "/api/tasks" in content
        assert "include_finalized" in content

    def test_non_empty(self):
        content = _JS.read_text(encoding="utf-8")
        assert len(content.strip()) > 200
