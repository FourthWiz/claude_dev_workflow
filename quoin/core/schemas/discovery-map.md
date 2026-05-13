# Discovery Map Schema Reference

JSON Schema: `quoin/core/schemas/discovery-map.schema.json`

## Purpose

The discovery map (`discovery-map.json`) is a portable structured snapshot of a quoin project's
layout, tasks, repositories, and memory. It enables automated tooling (future generators, dashboards,
cross-session reasoning agents) to understand project state without scanning the filesystem.

The map is produced by a future generator integrated with `/discover` (Phase 31+). The validator
`quoin/core/scripts/validate_discovery_map.py` checks map correctness now, independently of generation.
Source of truth for active state lives under `.workflow_artifacts/` at the project root.

## Top-level fields

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `schema_version` | int | yes | Schema version integer. Currently `1`. | `1` |
| `generated_at` | string (ISO 8601) | yes | Timestamp of map generation (timezone required). | `"2026-05-13T10:00:00Z"` |
| `project` | object | yes | Project identity. See `ProjectIdentity`. | `{"name": "quoin", ...}` |
| `artifact_roots` | object | yes | Paths to key artifact directories. See `ArtifactRoots`. | `{"workflow_artifacts_path": ".workflow_artifacts", ...}` |
| `memory` | object | yes | Paths to memory files. See `MemoryIndex`. | `{"lessons_learned": ".workflow_artifacts/memory/lessons-learned.md", ...}` |
| `tasks` | object | yes | Container with `active` and `finalized` task arrays. | `{"active": [...], "finalized": [...]}` |
| `repos` | array | yes | List of `RepoSummary` objects. | `[{"name": "quoin", ...}]` |
| `dependency_hints` | array | no | List of `DependencyHint` objects. | `[{"from_task": "a", "to_task": "b", "relation": "precedes"}]` |
| `freshness` | object | no | Object keyed by repo short-name; values are `FreshnessEntry`. | `{"quoin": {"head_sha": "abc...", "recorded_at": "...Z"}}` |
| `extensions` | object | no | Adapter-specific extension namespace. Any string key; values must be objects. | `{"claude": {"session_jsonl_dir": "~/.claude/..."}}` |

Unknown top-level keys are rejected by the validator (strict at top level). The `extensions` key is the
formal escape hatch for adapter-specific data.

## Field types

### ProjectIdentity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Project short name (e.g., `"quoin"`). |
| `root_path` | string | yes | **Absolute** OS-native path to project root. Only path-bearing field that is not repo-relative. |
| `runtime_adapters` | array of string | yes | Open-ended list of adapter names. Validator does not check adapter-name semantics. |
| `description` | string | no | Optional human-readable project description. |

### ArtifactRoots

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow_artifacts_path` | string | yes | Repo-relative path to `.workflow_artifacts/`. |
| `tasks_path` | string | yes | Repo-relative path to active tasks directory. |
| `finalized_path` | string | yes | Repo-relative path to finalized tasks directory. |
| `memory_path` | string | yes | Repo-relative path to memory directory. |
| `cache_path` | string | no | Repo-relative path to cache directory. Optional — absent if cache not yet built. |

### MemoryIndex

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lessons_learned` | string | yes | Repo-relative path to `lessons-learned.md`. |
| `daily_dir` | string | yes | Repo-relative path to daily briefings directory. |
| `weekly_dir` | string | yes | Repo-relative path to weekly briefings directory. |
| `sessions_dir` | string | yes | Repo-relative path to per-session state files directory. |
| `memory_md_index` | string | no | Optional repo-relative path to `MEMORY.md` index. |
| `staleness_path` | string | no | Optional repo-relative path to `_staleness.md`. Preferred over `repo_heads_path`. |
| `repo_heads_path` | string | no | Optional repo-relative path to legacy `repo-heads.md`. Fallback if `staleness_path` absent. |

### TaskSummary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Task name (kebab-case). |
| `status` | string enum | yes | `"active"` or `"finalized"`. |
| `path` | string | yes | Repo-relative path to task artifact directory. |
| `last_updated` | string (ISO 8601) | yes | Most recent update timestamp (timezone required). |
| `stages` | array of StageSummary | no | Optional stages list for multi-stage tasks. |
| `architecture_path` | string | no | Repo-relative path to `architecture.md`. |
| `current_plan_path` | string | no | Repo-relative path to `current-plan.md`. |

### StageSummary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | integer | yes | Stage number (1-based). |
| `path` | string | yes | Repo-relative path to stage artifact directory. |
| `status` | string enum | yes | `"pending"`, `"active"`, or `"finalized"`. |

### RepoSummary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Repository short name. |
| `path` | string | yes | Repo-relative path to repository root. |
| `head_sha` | string | yes | Full 40-character git SHA of HEAD. |
| `head_short` | string | yes | 7-character abbreviated git SHA. |
| `language` | string | no | Optional primary programming language. |
| `entry_points` | array of string | no | Optional list of repo-relative paths to entry-point files. |
| `cache_index_path` | string | no | Repo-relative path to cache `_index.md`. Absent if cache not built. |

### DependencyHint

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from_task` | string | yes | Source task name. |
| `to_task` | string | yes | Target task name. |
| `relation` | string enum | yes | `"references"`, `"precedes"`, or `"derives_from"`. |
| `note` | string | no | Optional human-readable note. |

### FreshnessEntry

The `freshness` top-level field is an object keyed by repo short-name (e.g., `"quoin"`).
Each value is a `FreshnessEntry`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `head_sha` | string | yes | Full git SHA at time of recording. |
| `recorded_at` | string (ISO 8601) | yes | Timestamp when freshness was recorded (timezone required). |
| `cache_updated_at` | string (ISO 8601) | no | Timestamp when cache was last updated. Absent if cache not built. |

Note: there is no `repo` field inside `FreshnessEntry` — the repo name is the key in the parent object.

## Path conventions

All path-bearing fields enumerated in `PATH_FIELDS` (see `validate_discovery_map.py`) are
**repo-relative strings**: POSIX-style forward slashes, no leading `./`, no trailing slash.

The PATH_FIELDS constant enumerates:
- `artifact_roots.workflow_artifacts_path`, `artifact_roots.tasks_path`, `artifact_roots.finalized_path`, `artifact_roots.memory_path`
- `artifact_roots.cache_path` (optional)
- `memory.lessons_learned`, `memory.daily_dir`, `memory.weekly_dir`, `memory.sessions_dir`
- `memory.memory_md_index`, `memory.staleness_path`, `memory.repo_heads_path` (all optional)
- `tasks.active[].path`, `tasks.active[].architecture_path`, `tasks.active[].current_plan_path` (last two optional)
- `tasks.active[].stages[].path`
- `tasks.finalized[].path`, `tasks.finalized[].architecture_path`, `tasks.finalized[].current_plan_path` (last two optional)
- `tasks.finalized[].stages[].path`
- `repos[].path`, `repos[].cache_index_path` (optional)
- `repos[].entry_points[]` (optional array; each element is a path string)

**The single exception** is `project.root_path`, which is an absolute OS-native path. This is the
only path-bearing field that is NOT repo-relative.

The rule deliberately says "fields enumerated in PATH_FIELDS" rather than "all `*_path` fields"
because several path-bearing fields do not carry the `_path` suffix (e.g., `memory.lessons_learned`,
`memory.daily_dir`, `repos[].entry_points[]`).

## Timestamp conventions

All ISO 8601 fields (`generated_at`, `last_updated`, `recorded_at`, `cache_updated_at`) must
include a timezone designator: either `Z` (UTC) or `±HH:MM`. UTC (`Z` suffix) is strongly preferred.

The validator in v1 checks the string type only — it does NOT enforce the timezone designator or
parse the timestamp format. Convention enforcement is prose-only in this document.

Future enhancement path (v2): add a regex check `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$`.

## Extensions namespace

The `extensions` object is an open-ended adapter-specific namespace. Contract:
- Any string key is permitted under `extensions`.
- Keys should follow the convention `extensions.<adapter-name>` (e.g., `extensions.claude`,
  `extensions.codex`, `extensions.gemini`).
- Values must be objects (the validator enforces this via DM-08).
- The validator silently accepts any structurally-valid `extensions` entry. It does NOT emit
  notes or warnings for non-conforming keys (e.g., typos like `extensions.claud`) — convention
  is prose-only. Do NOT encode adapter contracts here; adapters are opaque to the validator.
- Adding a new adapter requires only adding data to the map — no code change to the validator.

Example:
```json
{
  "extensions": {
    "claude": {
      "session_jsonl_dir": "~/.claude/projects/my-project/",
      "installed_skills_dir": "~/.claude/skills/"
    }
  }
}
```

## Compatibility (versioning)

The `schema_version` field is a monotonically-increasing integer. v1 is the initial version defined here.

Backward-incompatible changes (new required top-level fields, renamed enums, deleted fields) require
a `schema_version` bump to `2`. The validator checks `schema_version == 1` exactly; old validators
will reject v2 maps with `DM-04`.

Forward-compatible additions (new optional fields inside existing sub-objects) do NOT require a
version bump — the validator is permissive-inside for sub-objects (DM-03 strict mode applies only
at the top level). The `extensions` namespace is the formal escape hatch for adapter-specific data
that should never flow into the canonical schema.

## Future work (generator)

The generator that scans repos and emits `discovery-map.json` is **NOT implemented in Phase 30**.
This is an explicit out-of-scope decision (see `current-plan.md` Notes section, Phase 30 scope cap).

Phase 31+ work:
- Implement a generator integrated with `/discover` that reads `.workflow_artifacts/`, `git` state,
  and the knowledge cache to produce a valid `discovery-map.json`.
- When a second JSON validator is added in the future, extract shared scaffolding into
  `quoin/core/scripts/_validator_common.py` rather than duplicating exit-code/CLI conventions.
  Two validators is below the extraction threshold; three is not (see D-09 in Phase 30 plan).
- ISO 8601 format enforcement (add regex in validator v2; document timezone convention, enforce in v2).
- Optional `--strict` flag for `validate_discovery_map.py` that promotes prose-convention violations
  to errors (without a NOTE channel — cleaner API shape).
