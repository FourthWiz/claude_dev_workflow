"""lessons_guard.py — cross-project verbatim-duplicate guard for lessons-learned.md (IVG-119).

Catches the failure mode where a lesson entry authored for one project is copied
verbatim into another project's lessons-learned.md (evidence: a PricingCourse lesson
appearing verbatim in JobScraper's file). Complements the same-task heading-grep
idempotency check in /end_of_task and /sleep's dedup_against_lessons: grep catches
same-task re-appends; this guard catches DIFFERENT-task near-verbatim copies.

Portable-core: stdlib only, no `import quoin`, and deliberately does NOT import
sleep_score (adapter/core boundary) — the ≥4-char keyword tokenizer is copied, and the
shared slug inference is consumed by callers via `sleep_score.py --slug-from-path`.

Never blocks: exit 1 is a WARN signal the caller surfaces; the append still proceeds
on the caller's decision. Fail-OPEN on every error.

Exit codes (CLI):
  0 — no cross-project duplicate / safe / disabled / indeterminable-slug (fail-open)
  1 — suspected foreign duplicate (prints matched heading + slug)
  2 — argparse / invocation error (caller proceeds fail-OPEN + warn)
  3 — undeterminable (unreadable file — fail-OPEN)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

_ENV_DISABLE = "QUOIN_DISABLE_LESSONS_GUARD"
_ENV_THRESHOLD = "QUOIN_LESSONS_DUP_THRESHOLD"
_DEFAULT_THRESHOLD = 0.9

# Copied (NOT imported) from sleep_score._keywords — preserves the core-purity boundary.
_TOKEN_RE = re.compile(r"\b[a-zA-Z_-]{4,}\b")
# `## <date> — <task-name>` heading. Accepts em dash or hyphen separator.
_HEADING_RE = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}\s+[—-]\s+(.+?)\s*$", re.MULTILINE)
_STAGE_SUFFIX_RE = re.compile(r"\s*(?:\[[^\]]*\]|\(stage[^)]*\))\s*$", re.IGNORECASE)


def _keywords(text: str) -> set:
    return {w.lower() for w in _TOKEN_RE.findall(text)}


def _norm_slug(raw: str) -> str:
    """Normalize a task slug: strip a trailing stage marker, lower-case, collapse ws."""
    s = _STAGE_SUFFIX_RE.sub("", raw).strip()
    s = re.sub(r"\s+", " ", s).lower()
    return s


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _candidate_slug_from_text(candidate_text: str):
    m = _HEADING_RE.search(candidate_text)
    return _norm_slug(m.group(1)) if m else None


def _parse_lessons(lessons_text: str):
    """Yield (slug, body) for each `## <date> — <task>` entry in lessons_text."""
    entries = []
    matches = list(_HEADING_RE.finditer(lessons_text))
    for i, m in enumerate(matches):
        slug = _norm_slug(m.group(1))
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(lessons_text)
        entries.append((slug, lessons_text[body_start:body_end]))
    return entries


def _has_local_folder(lessons_root: Path, slug: str) -> bool:
    """True if slug has a local task folder (.workflow_artifacts/<slug> or finalized/<slug>)."""
    if lessons_root is None:
        return False
    wa = lessons_root / ".workflow_artifacts"
    try:
        for cand in (wa / slug, wa / "finalized" / slug):
            if cand.is_dir():
                return True
    except OSError:
        return False
    return False


def find_cross_project_duplicate(
    candidate_text,
    lessons_text,
    candidate_slug=None,
    *,
    strict_attrib=True,
    lessons_root=None,
    threshold=None,
):
    """Return a match dict for a suspected foreign duplicate, or None.

    A match requires: an existing lessons entry whose slug DIFFERS from the candidate's
    AND whose body is near-verbatim (token-set Jaccard >= threshold) to the candidate.
    With strict_attrib, the matched slug must ALSO have no local task folder (stronger
    foreign evidence). None-slug total contract: if the candidate slug cannot be
    determined (no heading and no candidate_slug), return None (fail-open, never a
    spurious WARN).
    """
    if threshold is None:
        threshold = _DEFAULT_THRESHOLD

    cand_slug = _norm_slug(candidate_slug) if candidate_slug else None
    if not cand_slug:
        cand_slug = _candidate_slug_from_text(candidate_text)
    if not cand_slug:
        return None  # None-slug total contract

    cand_tokens = _keywords(candidate_text)
    if not cand_tokens:
        return None

    best = None
    for slug, body in _parse_lessons(lessons_text):
        if slug == cand_slug:
            continue  # same project — not a cross-project signal
        sim = _jaccard(cand_tokens, _keywords(body))
        if sim < threshold:
            continue
        if strict_attrib and _has_local_folder(lessons_root, slug):
            continue  # slug is a real local task — weaker foreign evidence, skip
        if best is None or sim > best["jaccard"]:
            best = {"matched_slug": slug, "candidate_slug": cand_slug, "jaccard": sim}
    return best


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lessons_guard.py",
        description="Guard lessons-learned.md against cross-project verbatim duplication (IVG-119).",
    )
    parser.add_argument("--candidate-file", required=True, metavar="PATH",
                        help="File containing the lesson text about to be appended.")
    parser.add_argument("--lessons-file", required=True, metavar="PATH",
                        help="Path to the target lessons-learned.md.")
    parser.add_argument("--candidate-slug", default=None, metavar="SLUG",
                        help="Task slug of the candidate (usually the task name).")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--no-strict-attrib", dest="strict_attrib", action="store_false",
                        default=True,
                        help="Disable the no-local-folder corroboration (strict on by default).")
    return parser


def _threshold_from_env():
    raw = os.environ.get(_ENV_THRESHOLD)
    if not raw:
        return _DEFAULT_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_THRESHOLD


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if os.environ.get(_ENV_DISABLE) == "1":
        if args.format == "json":
            print(json.dumps({"disabled": True, "match": None}))
        else:
            print("lessons_guard: disabled via " + _ENV_DISABLE)
        return 0

    try:
        candidate_text = Path(args.candidate_file).read_text(encoding="utf-8")
        lessons_text = Path(args.lessons_file).read_text(encoding="utf-8")
    except OSError as exc:
        # Unreadable file → fail-OPEN (caller appends with a warn).
        print(f"lessons_guard: undeterminable — {exc}", file=sys.stderr)
        return 3

    lessons_root = None
    parts = Path(args.lessons_file).resolve().parts
    if ".workflow_artifacts" in parts:
        idx = parts.index(".workflow_artifacts")
        lessons_root = Path(*parts[:idx]) if idx > 0 else Path(parts[0])

    match = find_cross_project_duplicate(
        candidate_text,
        lessons_text,
        candidate_slug=args.candidate_slug,
        strict_attrib=args.strict_attrib,
        lessons_root=lessons_root,
        threshold=_threshold_from_env(),
    )

    if args.format == "json":
        print(json.dumps({"disabled": False, "match": match}))
        return 1 if match else 0

    if match is None:
        print("lessons_guard: OK — no cross-project duplicate detected")
        return 0

    print(
        "lessons_guard: WARN — candidate lesson (slug "
        f"'{match['candidate_slug']}') is near-verbatim (Jaccard "
        f"{match['jaccard']:.2f}) to an existing entry authored under a DIFFERENT "
        f"task slug '{match['matched_slug']}'. Suspected cross-project copy — verify "
        "before appending."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
