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

    def test_role_list_present(self):
        """index.html must have role="list" on the task-card-list container (T-09 MIN-A)."""
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert 'role="list"' in content, (
            'index.html missing role="list" on task-card-list container'
        )

    def test_aria_label_present(self):
        """index.html must have at least one aria-label attribute (T-09 MIN-A)."""
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "aria-label" in content, (
            "index.html missing aria-label attribute(s)"
        )


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

    def test_role_listitem_emitted(self):
        """app.js must emit role="listitem" on task card elements (T-09 MIN-A).

        role="listitem" is dynamically emitted (not in static index.html) — a T-08
        refactor that drops this attribute would silently break a11y with no other
        test catch. Assert the literal string is present in app.js source.
        """
        content = _JS.read_text(encoding="utf-8")
        assert 'role="listitem"' in content, (
            'app.js must emit role="listitem" on task card elements'
        )

    def test_non_empty(self):
        content = _JS.read_text(encoding="utf-8")
        assert len(content.strip()) > 200


class TestETagConditionalPolling:
    """IVG-76 T-06 asset tests: string-presence checks for ETag/304 client code.

    These are grep-only tests (no JS execution). Runtime correctness is covered
    by the server tests in test_dashboard_server.py.
    """

    def test_state_etags_present(self):
        """app.js must declare state.etags for ETag cache storage."""
        content = _JS.read_text(encoding="utf-8")
        assert "state.etags" in content, (
            "app.js must contain state.etags (ETag cache keyed by URL)"
        )

    def test_if_none_match_header_set(self):
        """app.js must send If-None-Match header on conditional requests."""
        content = _JS.read_text(encoding="utf-8")
        assert "If-None-Match" in content, (
            "app.js must call setRequestHeader('If-None-Match', ...) for conditional GET"
        )

    def test_304_handling_present(self):
        """app.js must handle xhr.status === 304 (skip DOM on Not Modified)."""
        content = _JS.read_text(encoding="utf-8")
        assert "304" in content, (
            "app.js must check xhr.status === 304 to skip DOM update on Not Modified"
        )

    def test_get_response_header_etag_present(self):
        """app.js must read ETag from response via getResponseHeader."""
        content = _JS.read_text(encoding="utf-8")
        assert "getResponseHeader" in content, (
            "app.js must use getResponseHeader to read ETag from response"
        )

    def test_no_eventsource_still_absent(self):
        """SSE is still cut — EventSource must remain absent after IVG-76 changes."""
        content = _JS.read_text(encoding="utf-8")
        assert "new EventSource" not in content
        assert "EventSource(" not in content

    def test_no_external_urls_after_ivg76(self):
        """IVG-76 changes must not introduce external URLs or CDN references."""
        content = _JS.read_text(encoding="utf-8")
        matches = _EXTERNAL_URL_RE.findall(content)
        assert not matches, f"app.js contains external URL(s) after IVG-76: {matches[:3]}"


# ---------------------------------------------------------------------------
# T-09: Memory browser asset tests
# ---------------------------------------------------------------------------

_MEMORY_JS = _ASSETS_DIR / "memory.js"
_DS_PATH_FOR_ASSETS = (
    Path(__file__).resolve().parents[2] / "scripts" / "dashboard_server.py"
)


class TestMemoryAssets:
    def test_memory_js_exists(self):
        """memory.js must exist in dashboard_assets/."""
        assert _MEMORY_JS.exists(), f"memory.js not found at {_MEMORY_JS}"

    def test_memory_js_no_external_urls(self):
        """memory.js must not reference external URLs or CDN."""
        content = _MEMORY_JS.read_text(encoding="utf-8")
        matches = _EXTERNAL_URL_RE.findall(content)
        assert not matches, f"memory.js contains external URL(s): {matches[:3]}"

    def test_index_html_references_memory_js(self):
        """index.html must include a <script src='./memory.js'> tag."""
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "memory.js" in content, "index.html does not reference memory.js"

    def test_index_html_memory_pane_section(self):
        """index.html must contain <section id='memory-pane'>."""
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert 'id="memory-pane"' in content or "id='memory-pane'" in content, (
            "index.html missing <section id='memory-pane'>"
        )

    def test_memory_js_asset_allowlist(self):
        """dashboard_server.py _ASSET_ALLOWLIST must include '/memory.js'."""
        source = _DS_PATH_FOR_ASSETS.read_text(encoding="utf-8")
        assert '"/memory.js"' in source or "'/memory.js'" in source, (
            "dashboard_server.py _ASSET_ALLOWLIST missing '/memory.js' entry"
        )

    def test_memory_js_no_etag_on_asset_send(self):
        """_send_asset() must NOT be modified to emit ETag for memory.js.

        ETag/If-None-Match applies only to /api/memory/* JSON responses, not static
        assets. Grep that _send_asset does not call send_header with ETag.
        """
        source = _DS_PATH_FOR_ASSETS.read_text(encoding="utf-8")
        # _send_asset() body must not contain 'ETag'
        import re
        # Find _send_asset function body (between def _send_asset and next top-level def)
        m = re.search(r'def _send_asset\(.*?\).*?(?=\n    def |\nclass |\Z)', source, re.DOTALL)
        if m:
            fn_body = m.group(0)
            assert "ETag" not in fn_body, (
                "_send_asset() must NOT emit ETag header — ETag is for /api/memory/* only"
            )

    def test_memory_js_etag_client_side_present(self):
        """memory.js must implement ETag/If-None-Match conditional polling."""
        content = _MEMORY_JS.read_text(encoding="utf-8")
        assert "If-None-Match" in content, "memory.js must send If-None-Match header"
        assert "304" in content, "memory.js must handle HTTP 304 Not Modified"
        assert "ETag" in content or "etag" in content, "memory.js must store/read ETag"

    def test_memory_js_esc_html_present(self):
        """memory.js must use escHtml (or equivalent) to prevent XSS."""
        content = _MEMORY_JS.read_text(encoding="utf-8")
        assert "escHtml" in content or "escape" in content.lower(), (
            "memory.js must escape HTML in rendered content (XSS prevention)"
        )

    def test_memory_js_no_eventsource(self):
        """memory.js must use polling not SSE (no EventSource)."""
        content = _MEMORY_JS.read_text(encoding="utf-8")
        assert "new EventSource" not in content
        assert "EventSource(" not in content

    def test_memory_bindings_in_server(self):
        """dashboard_server.py must bind list_memory, read_memory_item, memory_version_key."""
        source = _DS_PATH_FOR_ASSETS.read_text(encoding="utf-8")
        assert "list_memory = _dm.list_memory" in source, "list_memory not bound from _dm"
        assert "read_memory_item = _dm.read_memory_item" in source, "read_memory_item not bound"
        assert "memory_version_key = _dm.memory_version_key" in source, "memory_version_key not bound"

    def test_switch_type_clears_etag(self):
        """switchType() must delete memState.etags entry for the new type URL.

        Without this, a tab switch that follows a 304-cached fetch leaves the
        just-cleared list empty (the 304 returns no body). Fix added during IVG-87
        Playwright pass as a deviation from T-05 scope.
        """
        content = _MEMORY_JS.read_text(encoding="utf-8")
        assert "delete memState.etags" in content, (
            "memory.js switchType() must delete memState.etags to force full fetch on tab switch"
        )
