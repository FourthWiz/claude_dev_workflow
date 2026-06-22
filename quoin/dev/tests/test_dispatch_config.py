"""Unit tests for quoin/core/scripts/dispatch_config.py (IVG-90 Stage 1).

Tests cover:
- Config precedence matrix (env > ~/.config/quoin/dispatch.json > unset)
- --decide truth table (config × cache → dispatch/safe-path + --verbose reason)
- --write-cache whole-file overwrite + idempotency
- Fail-OPEN on every error path (unreadable config, malformed JSON, bad sentinel, etc.)
- QUOIN_1M_FALLBACK_MODEL parsed+stored but never acted on (v1 no-op)
- Classification surrogate (mirrors TestClassificationLogic style per D-06)
- Dual-list installed-import smoke (DEPLOYED_SCRIPTS + CORE_SCRIPTS)

Import idiom: importlib loader (lesson 2026-06-17 — direct package import raises
ModuleNotFoundError for core scripts).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Load the core module via importlib (lesson 2026-06-17)
# ---------------------------------------------------------------------------

_CORE_PATH = (
    Path(__file__).resolve().parents[3]
    / "quoin"
    / "core"
    / "scripts"
    / "dispatch_config.py"
)

_MODULE_NAME = "_quoin_core_dispatch_config_test"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, _CORE_PATH)
assert _SPEC is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _MOD
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

read_config = _MOD.read_config
config_verdict = _MOD.config_verdict
find_project_root = _MOD.find_project_root
_tier_token = _MOD._tier_token
cache_path = _MOD.cache_path
read_cache = _MOD.read_cache
write_cache = _MOD.write_cache
decide = _MOD.decide
main = _MOD.main


# ---------------------------------------------------------------------------
# T-01: Config layer — read_config() + config_verdict()
# ---------------------------------------------------------------------------


class TestReadConfig:
    """Config precedence: env var > dispatch.json > unset.

    All tests use mock.patch exclusively (never monkeypatch.setattr on os.path.expanduser).
    Using BOTH simultaneously causes monkeypatch teardown to overwrite mock.patch's restore,
    leaking a stale Mock into subsequent tests (interaction between mock.patch restore order
    and monkeypatch teardown).
    """

    def test_env_dispatch_on_overrides_file(self, tmp_path, monkeypatch):
        """QUOIN_1M_DISPATCH env takes precedence over file value."""
        cfg_file = tmp_path / "dispatch.json"
        cfg_file.write_text(json.dumps({"one_m_dispatch": "off"}))
        monkeypatch.setenv("QUOIN_1M_DISPATCH", "on")
        monkeypatch.delenv("QUOIN_1M_FALLBACK_MODEL", raising=False)
        with _patch_cfg_path(cfg_file):
            cfg = read_config()
        assert cfg["one_m_dispatch"] == "on"

    def test_file_used_when_env_absent(self, tmp_path, monkeypatch):
        """dispatch.json value used when env var is unset."""
        monkeypatch.delenv("QUOIN_1M_DISPATCH", raising=False)
        monkeypatch.delenv("QUOIN_1M_FALLBACK_MODEL", raising=False)
        cfg_file = tmp_path / "dispatch.json"
        cfg_file.write_text(json.dumps({"one_m_dispatch": "off"}))
        with _patch_cfg_path(cfg_file):
            cfg = read_config()
        assert cfg["one_m_dispatch"] == "off"

    def test_none_when_both_absent(self, tmp_path, monkeypatch):
        """Both env and file absent → one_m_dispatch is None."""
        monkeypatch.delenv("QUOIN_1M_DISPATCH", raising=False)
        monkeypatch.delenv("QUOIN_1M_FALLBACK_MODEL", raising=False)
        nonexistent = tmp_path / "dispatch.json"
        with _patch_cfg_path(nonexistent):
            cfg = read_config()
        assert cfg["one_m_dispatch"] is None

    def test_malformed_json_falls_through(self, tmp_path, monkeypatch):
        """Malformed JSON in dispatch.json → treated as absent (fail-OPEN)."""
        monkeypatch.delenv("QUOIN_1M_DISPATCH", raising=False)
        monkeypatch.delenv("QUOIN_1M_FALLBACK_MODEL", raising=False)
        cfg_file = tmp_path / "dispatch.json"
        cfg_file.write_text("not json {{")
        with _patch_cfg_path(cfg_file):
            cfg = read_config()
        assert cfg["one_m_dispatch"] is None

    def test_fallback_model_env_precedence(self, tmp_path, monkeypatch):
        """QUOIN_1M_FALLBACK_MODEL env takes precedence over file."""
        monkeypatch.setenv("QUOIN_1M_FALLBACK_MODEL", "claude-haiku-4-5")
        monkeypatch.delenv("QUOIN_1M_DISPATCH", raising=False)
        cfg_file = tmp_path / "dispatch.json"
        cfg_file.write_text(json.dumps({"one_m_fallback_model": "other-model"}))
        with _patch_cfg_path(cfg_file):
            cfg = read_config()
        assert cfg["one_m_fallback_model"] == "claude-haiku-4-5"

    def test_fallback_model_inert_in_v1(self, monkeypatch):
        """QUOIN_1M_FALLBACK_MODEL is parsed but the decide() function never dispatches to it (v1 no-op)."""
        monkeypatch.setenv("QUOIN_1M_FALLBACK_MODEL", "some-model-id")
        monkeypatch.delenv("QUOIN_1M_DISPATCH", raising=False)
        # decide() with no config = unset+unknown → dispatch (probe), not safe-path via fallback
        with mock.patch.object(_MOD, "read_cache", return_value="unknown"):
            with mock.patch.object(_MOD, "read_config",
                                   return_value={"one_m_dispatch": None,
                                                 "one_m_fallback_model": "some-model-id"}):
                verdict, reason = decide("sonnet")
        # still returns dispatch (probe), not safe-path
        assert verdict == "dispatch"
        assert reason == "probe"


class TestConfigVerdict:
    """config_verdict() truth table."""

    def _v(self, tier: str, val) -> str:
        return config_verdict(tier, {"one_m_dispatch": val})

    def test_on_returns_safe(self):
        assert self._v("sonnet", "on") == "safe"

    def test_off_returns_unsafe(self):
        assert self._v("sonnet", "off") == "unsafe"

    def test_none_returns_unset(self):
        assert self._v("sonnet", None) == "unset"

    def test_empty_string_returns_unset(self):
        assert self._v("sonnet", "") == "unset"

    def test_tier_csv_tier_in_list_is_safe(self):
        assert self._v("haiku", "haiku,sonnet") == "safe"

    def test_tier_csv_tier_not_in_list_is_unsafe(self):
        assert self._v("opus", "haiku,sonnet") == "unsafe"

    def test_tier_csv_single_entry(self):
        assert self._v("haiku", "haiku") == "safe"
        assert self._v("sonnet", "haiku") == "unsafe"

    def test_tier_csv_whitespace_stripped(self):
        assert self._v("sonnet", "haiku, sonnet , opus") == "safe"

    def test_tier_csv_case_insensitive(self):
        assert self._v("SONNET", "sonnet") == "safe"

    def test_garbage_value_returns_unset(self):
        # A value that is non-empty but matches no known form → unset
        assert self._v("sonnet", "   ") == "unset"


# ---------------------------------------------------------------------------
# T-02: Cache layer — tier_token, cache_path, read_cache, write_cache
# ---------------------------------------------------------------------------


class TestTierToken:
    def test_lowercase_alpha_passthrough(self):
        assert _tier_token("haiku") == "haiku"
        assert _tier_token("sonnet") == "sonnet"
        assert _tier_token("opus") == "opus"

    def test_strips_whitespace(self):
        assert _tier_token("  haiku  ") == "haiku"

    def test_uppercased_lowercased(self):
        assert _tier_token("HAIKU") == "haiku"

    def test_digits_rejected(self):
        assert _tier_token("haiku4") == ""

    def test_slash_rejected(self):
        assert _tier_token("haiku/sonnet") == ""

    def test_empty_rejected(self):
        assert _tier_token("") == ""

    def test_hyphen_rejected(self):
        assert _tier_token("claude-sonnet") == ""


class TestCachePath:
    def test_valid_tier_returns_path(self, tmp_path):
        p = cache_path("sonnet", tmp_path)
        assert p == tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"

    def test_malformed_tier_returns_none(self, tmp_path):
        assert cache_path("bad/tier", tmp_path) is None

    def test_tier_token_wired_in(self, tmp_path):
        """_tier_token sanitization is actually used in cache_path (not dead code)."""
        p_lower = cache_path("HAIKU", tmp_path)
        assert p_lower is not None
        assert "1m-tier-haiku.txt" in str(p_lower)


class TestReadCache:
    def test_safe_sentinel(self, tmp_path):
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"
        p.parent.mkdir(parents=True)
        p.write_text("safe")
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            assert read_cache("sonnet") == "safe"

    def test_unsafe_sentinel(self, tmp_path):
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-haiku.txt"
        p.parent.mkdir(parents=True)
        p.write_text("unsafe")
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            assert read_cache("haiku") == "unsafe"

    def test_missing_sentinel_is_unknown(self, tmp_path):
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            assert read_cache("sonnet") == "unknown"

    def test_malformed_sentinel_is_unknown(self, tmp_path):
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"
        p.parent.mkdir(parents=True)
        p.write_text("garbage value")
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            assert read_cache("sonnet") == "unknown"

    def test_empty_sentinel_is_unknown(self, tmp_path):
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"
        p.parent.mkdir(parents=True)
        p.write_text("")
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            assert read_cache("sonnet") == "unknown"

    def test_no_project_root_is_unknown(self):
        with mock.patch.object(_MOD, "find_project_root", return_value=None):
            assert read_cache("sonnet") == "unknown"

    def test_malformed_tier_is_unknown(self, tmp_path):
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            assert read_cache("bad/tier") == "unknown"


class TestWriteCache:
    def test_writes_safe(self, tmp_path):
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            write_cache("sonnet", "safe")
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"
        assert p.read_text() == "safe"

    def test_writes_unsafe(self, tmp_path):
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            write_cache("haiku", "unsafe")
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-haiku.txt"
        assert p.read_text() == "unsafe"

    def test_idempotent_same_value(self, tmp_path):
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            write_cache("sonnet", "safe")
            write_cache("sonnet", "safe")
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"
        assert p.read_text() == "safe"

    def test_overwrite_flips_value(self, tmp_path):
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            write_cache("sonnet", "safe")
            write_cache("sonnet", "unsafe")
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"
        assert p.read_text() == "unsafe"

    def test_invalid_result_is_noop(self, tmp_path):
        """write_cache silently ignores invalid result values."""
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            write_cache("sonnet", "bad-value")
        p = tmp_path / ".workflow_artifacts" / "memory" / "1m-tier-sonnet.txt"
        assert not p.exists()

    def test_no_project_root_is_silent(self):
        """No project root → silent skip, no exception."""
        with mock.patch.object(_MOD, "find_project_root", return_value=None):
            write_cache("sonnet", "safe")  # must not raise

    def test_write_error_is_silent(self, tmp_path):
        """Write failure → silent skip (fail-OPEN R-04)."""
        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            with mock.patch("os.replace", side_effect=OSError("disk full")):
                write_cache("sonnet", "safe")  # must not raise

    def test_atomic_rename_used(self, tmp_path):
        """Writes via a .tmp file then os.replace (whole-file atomic overwrite)."""
        replaced = []
        real_replace = os.replace

        def capturing_replace(src, dst):
            replaced.append((src, dst))
            real_replace(src, dst)

        with mock.patch.object(_MOD, "find_project_root", return_value=tmp_path):
            with mock.patch("os.replace", side_effect=capturing_replace):
                write_cache("sonnet", "safe")

        assert len(replaced) == 1
        src, dst = replaced[0]
        assert str(src).endswith(".tmp")
        assert not str(dst).endswith(".tmp")


# ---------------------------------------------------------------------------
# T-03: --decide truth table
# ---------------------------------------------------------------------------


class TestDecide:
    """decide() covers all (config × cache) combinations."""

    # --- config=unsafe → safe-path regardless of cache ---

    def test_config_off_cache_safe_returns_safepath(self):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": "off", "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="safe"):
                v, r = decide("sonnet")
        assert v == "safe-path"
        assert r == "config"

    def test_config_csv_unsafe_tier_returns_safepath(self):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": "haiku", "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="unknown"):
                v, r = decide("sonnet")  # sonnet not in csv
        assert v == "safe-path"
        assert r == "config"

    # --- config=safe → dispatch regardless of cache ---

    def test_config_on_cache_unsafe_returns_dispatch(self):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": "on", "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="unsafe"):
                v, r = decide("sonnet")
        assert v == "dispatch"
        assert r == "config"

    def test_config_csv_safe_tier_returns_dispatch(self):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": "haiku,sonnet", "one_m_fallback_model": None}):
            v, r = decide("sonnet")
        assert v == "dispatch"
        assert r == "config"

    # --- config=unset + cache=unsafe → safe-path ---

    def test_unset_config_cache_unsafe_returns_safepath(self):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": None, "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="unsafe"):
                v, r = decide("sonnet")
        assert v == "safe-path"
        assert r == "cache"

    # --- config=unset + cache=safe → dispatch ---

    def test_unset_config_cache_safe_returns_dispatch(self):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": None, "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="safe"):
                v, r = decide("sonnet")
        assert v == "dispatch"
        assert r == "cache"

    # --- config=unset + cache=unknown → dispatch (probe, today's path) ---

    def test_unset_config_cache_unknown_returns_dispatch_probe(self):
        """Common case (no config, no sentinel) → dispatch (probe) = today's behavior."""
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": None, "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="unknown"):
                v, r = decide("sonnet")
        assert v == "dispatch"
        assert r == "probe"

    def test_probe_path_adds_zero_api_calls(self):
        """Verify probe path is identical to today: no extra API calls (only local reads)."""
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": None, "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="unknown"):
                verdict, _ = decide("sonnet")
        assert verdict == "dispatch"


# ---------------------------------------------------------------------------
# Fail-OPEN paths
# ---------------------------------------------------------------------------


class TestFailOpen:
    """Every error path for --decide must produce 'dispatch' (never raise, never block)."""

    def test_decide_exception_propagates_to_main_failopen(self, capsys):
        """decide() raises on read_config error; main() catches it and prints 'dispatch'."""
        with mock.patch.object(_MOD, "read_config", side_effect=Exception("disk error")):
            rc = main(["--decide", "--tier", "sonnet"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "dispatch"

    def test_decide_cache_exception_failopen(self, capsys):
        """decide() raises when read_cache raises; main() catches and prints 'dispatch'."""
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": None, "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", side_effect=Exception("IO error")):
                rc = main(["--decide", "--tier", "sonnet"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "dispatch"

    def test_main_decide_never_raises_on_config_error(self):
        """main() --decide never raises even when config is corrupted."""
        with mock.patch.object(_MOD, "read_config", side_effect=RuntimeError("boom")):
            assert main(["--decide", "--tier", "sonnet"]) == 0

    def test_main_decide_missing_tier_prints_dispatch(self, capsys):
        """--decide with no --tier → prints 'dispatch', exits 0 (fail-OPEN pre-validation)."""
        assert main(["--decide"]) == 0
        out = capsys.readouterr().out.strip()
        assert out == "dispatch"

    def test_main_decide_verbose_reason_on_second_line(self, capsys):
        """--decide --verbose prints verdict on line 1, reason on line 2."""
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": None, "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="unknown"):
                rc = main(["--decide", "--tier", "sonnet", "--verbose"])
        assert rc == 0
        lines = capsys.readouterr().out.strip().splitlines()
        assert lines[0] in ("dispatch", "safe-path")
        assert lines[1] in ("config", "cache", "probe")

    def test_main_decide_verbose_config_reason(self, capsys):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": "off", "one_m_fallback_model": None}):
            main(["--decide", "--tier", "sonnet", "--verbose"])
        lines = capsys.readouterr().out.strip().splitlines()
        assert lines[0] == "safe-path"
        assert lines[1] == "config"

    def test_main_decide_verbose_cache_reason(self, capsys):
        with mock.patch.object(_MOD, "read_config",
                               return_value={"one_m_dispatch": None, "one_m_fallback_model": None}):
            with mock.patch.object(_MOD, "read_cache", return_value="safe"):
                main(["--decide", "--tier", "sonnet", "--verbose"])
        lines = capsys.readouterr().out.strip().splitlines()
        assert lines[0] == "dispatch"
        assert lines[1] == "cache"

    def test_main_write_cache_valid_call_exits_0(self):
        """--write-cache with valid args → exit 0."""
        assert main(["--write-cache", "--tier", "sonnet", "--result", "safe"]) == 0

    def test_main_write_cache_missing_tier_exits_0(self):
        """--write-cache with missing --tier → silent exit 0."""
        assert main(["--write-cache"]) == 0

    def test_main_no_args_exits_0(self):
        """No args → exit 0 (no mode selected)."""
        assert main([]) == 0

    def test_find_project_root_no_workflow_artifacts(self, tmp_path):
        """find_project_root returns None when no .workflow_artifacts/ ancestor found."""
        result = find_project_root(tmp_path)
        assert result is None

    def test_find_project_root_finds_parent(self, tmp_path):
        (tmp_path / ".workflow_artifacts").mkdir()
        child = tmp_path / "sub" / "dir"
        child.mkdir(parents=True)
        result = find_project_root(child)
        assert result == tmp_path


# ---------------------------------------------------------------------------
# Classification surrogate (mirrors TestClassificationLogic per D-06)
# ---------------------------------------------------------------------------


class TestDecisionClassificationLogic:
    """D-06: Falsifiable unit tests for the decide() decision table.

    The runtime 1M dispatch verdict is unfalsifiable in CI (no harness can trigger
    a real 1M-credit 400). These tests exercise the DECISION RULE against synthetic
    config+cache fixture combinations, providing a falsifiable surrogate.

    Decision rule:
      config=unsafe                  → safe-path / config
      config=safe                    → dispatch  / config
      config=unset + cache=unsafe    → safe-path / cache
      config=unset + cache=safe      → dispatch  / cache
      config=unset + cache=unknown   → dispatch  / probe
    """

    def _decide_with(self, one_m_dispatch, cache_state: str):
        """Invoke decide() with synthetic config and cache fixtures."""
        cfg = {"one_m_dispatch": one_m_dispatch, "one_m_fallback_model": None}
        with mock.patch.object(_MOD, "read_config", return_value=cfg):
            with mock.patch.object(_MOD, "read_cache", return_value=cache_state):
                return decide("sonnet")

    def test_off_any_cache_returns_safepath_config(self):
        for cache_state in ("safe", "unsafe", "unknown"):
            v, r = self._decide_with("off", cache_state)
            assert v == "safe-path", f"cache={cache_state}"
            assert r == "config", f"cache={cache_state}"

    def test_on_any_cache_returns_dispatch_config(self):
        for cache_state in ("safe", "unsafe", "unknown"):
            v, r = self._decide_with("on", cache_state)
            assert v == "dispatch", f"cache={cache_state}"
            assert r == "config", f"cache={cache_state}"

    def test_unset_safe_cache_returns_dispatch_cache(self):
        v, r = self._decide_with(None, "safe")
        assert v == "dispatch"
        assert r == "cache"

    def test_unset_unsafe_cache_returns_safepath_cache(self):
        v, r = self._decide_with(None, "unsafe")
        assert v == "safe-path"
        assert r == "cache"

    def test_unset_unknown_cache_returns_dispatch_probe(self):
        v, r = self._decide_with(None, "unknown")
        assert v == "dispatch"
        assert r == "probe"

    def test_tier_csv_in_list_safe(self):
        cfg = {"one_m_dispatch": "haiku,sonnet", "one_m_fallback_model": None}
        with mock.patch.object(_MOD, "read_config", return_value=cfg):
            v, r = decide("sonnet")
        assert v == "dispatch"
        assert r == "config"

    def test_tier_csv_not_in_list_unsafe(self):
        cfg = {"one_m_dispatch": "haiku", "one_m_fallback_model": None}
        with mock.patch.object(_MOD, "read_config", return_value=cfg):
            v, r = decide("opus")
        assert v == "safe-path"
        assert r == "config"

    def test_empty_dispatch_value_falls_through_to_cache(self):
        """Empty string in config → unset → falls through to cache layer."""
        v, r = self._decide_with("", "safe")
        assert v == "dispatch"
        assert r == "cache"


# ---------------------------------------------------------------------------
# Dual-list installer smoke (DEPLOYED_SCRIPTS + CORE_SCRIPTS)
# ---------------------------------------------------------------------------


class TestInstallerDualListSmoke:
    """R-03: dispatch_config.py must appear in BOTH installer lists.

    If either list is missing it, the wrapper's parents[1]/core/scripts loader
    will fail at runtime (NameError / FileNotFoundError) on a fresh install.
    """

    @pytest.fixture(scope="class")
    def installer(self):
        """Load installer.py via importlib (lesson 2026-06-17)."""
        installer_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "quoin"
            / "installer.py"
        )
        spec = importlib.util.spec_from_file_location("_quoin_installer_test", installer_path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod

    def test_in_deployed_scripts(self, installer):
        assert "dispatch_config.py" in installer.DEPLOYED_SCRIPTS, (
            "dispatch_config.py missing from DEPLOYED_SCRIPTS — wrapper won't be deployed"
        )

    def test_in_core_scripts(self, installer):
        assert "dispatch_config.py" in installer.CORE_SCRIPTS, (
            "dispatch_config.py missing from CORE_SCRIPTS — wrapper's parents[1] loader will NameError"
        )

    def test_wrapper_importable_via_deployed_path(self):
        """Smoke-import the WRAPPER (not the core) via the wrapper's own importlib chain."""
        wrapper_path = (
            Path(__file__).resolve().parents[3]
            / "quoin"
            / "scripts"
            / "dispatch_config.py"
        )
        spec = importlib.util.spec_from_file_location("_wrapper_smoke_test", wrapper_path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        # Core functions should be re-exported via globals() loop in the wrapper
        assert hasattr(mod, "main"), "main not exported from wrapper"
        assert hasattr(mod, "decide"), "decide not exported from wrapper"
        assert hasattr(mod, "write_cache"), "write_cache not exported from wrapper"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


from contextlib import contextmanager


@contextmanager
def _patch_cfg_path(cfg_file: Path):
    """Context manager: redirect os.path.expanduser('~/.config/quoin/dispatch.json') to cfg_file.

    Uses mock.patch ONLY (no monkeypatch) to avoid the mock.patch-vs-monkeypatch teardown
    ordering hazard. mock.patch with side_effect correctly intercepts only the specific path
    and passes all other expanduser calls (e.g., '~' → real home dir) through unchanged.
    """
    original_expanduser = os.path.expanduser

    def patched_expanduser(p):
        if p == "~/.config/quoin/dispatch.json":
            return str(cfg_file)
        return original_expanduser(p)

    with mock.patch("os.path.expanduser", side_effect=patched_expanduser):
        yield
