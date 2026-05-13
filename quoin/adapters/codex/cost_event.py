#!/usr/bin/env python3
"""Write and validate repo-local Codex cost ledger events.

This adapter records only the telemetry Quoin can know from a repo-local Codex
workflow invocation. Codex token counts and dollar costs are not exposed through
a verified local Quoin interface in this repository, so the writer marks those
fields as not_available inside the ledger note instead of guessing.

Usage:
    python3 quoin/adapters/codex/cost_event.py write --project-root . --task my-task --phase plan --effort high
    python3 quoin/adapters/codex/cost_event.py validate --project-root . --task my-task --expect-codex
    python3 quoin/adapters/codex/cost_event.py --self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


SCRIPT_DIR = Path(__file__).resolve().parent
QUOIN_PKG_DIR = SCRIPT_DIR.parent.parent
CORE_COST_EVENT_PATH = QUOIN_PKG_DIR / "core" / "scripts" / "cost_event.py"

ALLOWED_EFFORTS = {"low", "medium", "high", "max", "unknown"}
REQUIRED_NOTE_FIELDS = {
    "runtime",
    "task",
    "timestamp",
    "session_id",
    "effort",
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "total_tokens",
    "cost_usd",
    "telemetry_source",
}
UNAVAILABLE_FIELDS = {
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "total_tokens",
    "cost_usd",
    "telemetry_source",
}


def _load_cost_event_module():
    spec = importlib.util.spec_from_file_location(
        "_quoin_core_cost_event_for_codex_adapter",
        CORE_COST_EVENT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load portable cost event module: {CORE_COST_EVENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_COST_EVENT = _load_cost_event_module()
CostEvent = _COST_EVENT.CostEvent
format_row = _COST_EVENT.format_row
parse_row = _COST_EVENT.parse_row
iter_events = _COST_EVENT.iter_events


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: List[str]
    codex_events: int = 0


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    value = value.replace("|", "/")
    value = value.replace(";", ",")
    return value or "unknown"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip())
    return slug.strip("-") or "unknown"


def _date_from_timestamp(timestamp: str) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})T", timestamp)
    if not match:
        raise ValueError("timestamp must start with ISO datetime YYYY-MM-DDT...")
    return match.group(1)


def _ledger_path(project_root: Path, task: str) -> Path:
    task = _slug(task)
    return project_root / ".workflow_artifacts" / task / "cost-ledger.md"


def build_codex_event(
    *,
    task: str,
    phase: str,
    effort: str,
    session_id: str = "unknown",
    timestamp: str | None = None,
    note: str = "",
    fallback_fires: int = 0,
) -> object:
    if effort not in ALLOWED_EFFORTS:
        raise ValueError(f"effort must be one of {sorted(ALLOWED_EFFORTS)}")
    if fallback_fires < 0:
        raise ValueError("fallback_fires must be non-negative")

    timestamp = timestamp or _now_timestamp()
    date = _date_from_timestamp(timestamp)
    clean_session_id = _sanitize_value(session_id)
    uuid_suffix = _slug(clean_session_id if clean_session_id != "unknown" else timestamp)
    ledger_uuid = f"unknown-codex-{uuid_suffix}"

    note_fields = {
        "runtime": "codex",
        "task": _sanitize_value(task),
        "timestamp": _sanitize_value(timestamp),
        "session_id": clean_session_id,
        "effort": effort,
        "input_tokens": "not_available",
        "output_tokens": "not_available",
        "cache_creation_input_tokens": "not_available",
        "cache_read_input_tokens": "not_available",
        "total_tokens": "not_available",
        "cost_usd": "not_available",
        "telemetry_source": "not_available",
    }
    if note:
        note_fields["note"] = _sanitize_value(note)

    note_text = "; ".join(f"{key}={value}" for key, value in note_fields.items())
    return CostEvent(
        uuid=ledger_uuid,
        date=date,
        phase=_sanitize_value(phase),
        model_or_effort=effort,
        category="task",
        note=note_text,
        fallback_fires=fallback_fires,
    )


def _parse_note_fields(note: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for part in note.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _validate_codex_event(event: object, *, source: str) -> List[str]:
    errors: List[str] = []
    note_fields = _parse_note_fields(event.note)

    if note_fields.get("runtime") != "codex":
        return errors

    if not event.uuid.startswith("unknown-codex-"):
        errors.append(f"{source}: Codex event uuid must start with unknown-codex-")
    if event.category != "task":
        errors.append(f"{source}: category must be task")
    if event.model_or_effort not in ALLOWED_EFFORTS:
        errors.append(f"{source}: effort must be one of {sorted(ALLOWED_EFFORTS)}")
    if event.fallback_fires < 0:
        errors.append(f"{source}: fallback_fires must be non-negative")

    missing = sorted(REQUIRED_NOTE_FIELDS - set(note_fields))
    if missing:
        errors.append(f"{source}: Codex note missing required fields {missing}")

    for field in sorted(UNAVAILABLE_FIELDS):
        if note_fields.get(field) != "not_available":
            errors.append(f"{source}: {field} must be not_available for Codex")

    timestamp = note_fields.get("timestamp", "")
    try:
        timestamp_date = _date_from_timestamp(timestamp)
    except ValueError:
        errors.append(f"{source}: timestamp must start with ISO datetime YYYY-MM-DDT...")
    else:
        if timestamp_date != event.date:
            errors.append(f"{source}: event date must match timestamp date")

    if note_fields.get("effort") and note_fields["effort"] != event.model_or_effort:
        errors.append(f"{source}: note effort must match model_or_effort column")

    return errors


def _append_event(ledger: Path, task: str, event: object) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    if not ledger.exists():
        ledger.write_text(f"# Cost Ledger - {task}\n", encoding="utf-8")

    row = format_row(event)
    parsed = parse_row(row, source=str(ledger), lineno=0)
    if parsed is None:
        raise RuntimeError("portable cost event parser rejected the generated row")
    codex_errors = _validate_codex_event(parsed, source=str(ledger))
    if codex_errors:
        raise RuntimeError("; ".join(codex_errors))

    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(row + "\n")


def validate_ledger(ledger: Path, *, expect_codex: bool = False) -> ValidationResult:
    errors: List[str] = []
    codex_events = 0
    if not ledger.is_file():
        return ValidationResult(False, [f"ledger file does not exist: {ledger}"], 0)

    with ledger.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            event = parse_row(line, source=str(ledger), lineno=lineno)
            if event is None:
                continue
            note_fields = _parse_note_fields(event.note)
            if note_fields.get("runtime") != "codex":
                continue
            codex_events += 1
            errors.extend(_validate_codex_event(event, source=f"{ledger}:{lineno}"))

    if expect_codex and codex_events == 0:
        errors.append(f"{ledger}: no Codex cost events found")

    return ValidationResult(not errors, errors, codex_events)


def run_self_test() -> ValidationResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        event = build_codex_event(
            task="phase-35-codex-cost",
            phase="plan",
            effort="high",
            timestamp="2026-05-13T10:11:12Z",
            note="self-test",
        )
        ledger = _ledger_path(root, "phase-35-codex-cost")
        _append_event(ledger, "phase-35-codex-cost", event)
        return validate_ledger(ledger, expect_codex=True)


def _print_validation(result: ValidationResult) -> int:
    if result.ok:
        print(f"CODEX COST PASS: {result.codex_events} Codex event(s) valid")
        return 0
    for error in result.errors:
        print(f"CODEX COST FAIL: {error}", file=sys.stderr)
    return 1


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Write and validate a temporary Codex cost event.",
    )
    sub = parser.add_subparsers(dest="command")

    write_parser = sub.add_parser("write", help="Append a Codex cost event row")
    write_parser.add_argument("--project-root", default=".")
    write_parser.add_argument("--task", required=True)
    write_parser.add_argument("--phase", required=True)
    write_parser.add_argument("--effort", required=True, choices=sorted(ALLOWED_EFFORTS))
    write_parser.add_argument("--session-id", default="unknown")
    write_parser.add_argument("--timestamp")
    write_parser.add_argument("--note", default="")
    write_parser.add_argument("--fallback-fires", type=int, default=0)
    write_parser.add_argument("--dry-run", action="store_true")

    validate_parser = sub.add_parser("validate", help="Validate Codex cost events")
    validate_parser.add_argument("--project-root", default=".")
    validate_target = validate_parser.add_mutually_exclusive_group(required=True)
    validate_target.add_argument("--task")
    validate_target.add_argument("--ledger")
    validate_parser.add_argument("--expect-codex", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.self_test:
        return _print_validation(run_self_test())

    if args.command == "write":
        project_root = Path(args.project_root).resolve()
        event = build_codex_event(
            task=args.task,
            phase=args.phase,
            effort=args.effort,
            session_id=args.session_id,
            timestamp=args.timestamp,
            note=args.note,
            fallback_fires=args.fallback_fires,
        )
        row = format_row(event)
        if args.dry_run:
            print(row)
            return 0
        ledger = _ledger_path(project_root, args.task)
        _append_event(ledger, args.task, event)
        print(f"CODEX COST WROTE: {ledger}")
        print(row)
        return 0

    if args.command == "validate":
        project_root = Path(args.project_root).resolve()
        ledger = Path(args.ledger).resolve() if args.ledger else _ledger_path(project_root, args.task)
        return _print_validation(validate_ledger(ledger, expect_codex=args.expect_codex))

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
