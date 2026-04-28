#!/usr/bin/env python3
"""
audit_corpus_coverage.py — Empirical residual canary for classify_critic_issues.py parser.

Reads every fixture under quoin/dev/tests/fixtures/classify_critic_issues/training/,
runs the union parser (Shapes A–E) against each file, and emits a residual report
listing every issue-bullet line that matched no Shape.

"Issue bullet" means:
  - inside the ## Issues H2 block,
  - under a standard severity H3 (Critical / Major / Minor),
  - at top-level indent (not a deeply-indented sub-bullet).

Exit code:
  0 — all issue bullets matched (residual is empty)
  1 — at least one unrecognized issue bullet (non-empty residual)

Output format (one line per unrecognized bullet):
  <filename>:<line>: <full bullet text>

Usage:
  python3 audit_corpus_coverage.py [--training-dir <path>]

By default, resolves training dir relative to this script's location:
  <script_dir>/tests/fixtures/classify_critic_issues/training/
"""

import argparse
import os
import re
import sys

# ── Bullet-shape regexes (mirrors classify_critic_issues.py SHAPE_PATTERNS) ──
# First-match-wins ordering: A → B → C → D → E.

# Shape A: bracket form  - **[CRIT-1] title** or - **[MAJ-1-r2 (NEW)] title**
_SHAPE_A = re.compile(
    r'^-\s+\*\*\[(?:CRIT|MAJ|MIN|NIT)-[0-9]+(?:[A-Za-z0-9-]*(?:\s*\([^)]*\))?)?'
    r'\]\s+.+?\*\*',
    re.IGNORECASE,
)

# Shape B: no-bracket em-dash  - **CRIT-2 — title**  (also handles round suffix)
_SHAPE_B = re.compile(
    r'^-\s+\*\*(?:CRIT|MAJ|MIN|NIT)-[0-9]+(?:[A-Za-z0-9-]*(?:\s*\([^)]*\))?)?'
    r'\s*[—–-]\s+.+?\*\*',
    re.IGNORECASE,
)

# Shape C: Issue prefix  - **Issue C1 — title**
_SHAPE_C = re.compile(
    r'^-\s+\*\*Issue\s+[A-Za-z]+[A-Za-z0-9-]*\s*[—–-]\s+.+?\*\*',
    re.IGNORECASE,
)

# Shape D: full-word severity  - **MAJOR — title.**
_SHAPE_D = re.compile(
    r'^-\s+\*\*(?:CRITICAL|MAJOR|MINOR)\s*[—–-]\s+.+?\.?\*\*',
    re.IGNORECASE,
)

# Shape E: colon separator  - **MIN-1: title.**  (seen in stage-3 critic-response-5)
_SHAPE_E = re.compile(
    r'^-\s+\*\*(?:CRIT|MAJ|MIN|NIT)-[0-9]+(?:[A-Za-z0-9-]*)?\s*:\s+.+?\*\*',
    re.IGNORECASE,
)

SHAPES = [_SHAPE_A, _SHAPE_B, _SHAPE_C, _SHAPE_D, _SHAPE_E]

# Standard severity H3 headings (case-insensitive prefix match)
_SEVERITY_H3 = re.compile(r'^###\s+(?:Critical|Major|Minor)\b', re.IGNORECASE)
# Any H3 heading (including non-severity ones that end a severity block)
_ANY_H3 = re.compile(r'^###\s+\S')
# H2 heading: starts a new top-level section
_H2 = re.compile(r'^##\s+\S')
# Top-level issue bullet: starts with "- **" (no leading indent)
_TOP_BULLET = re.compile(r'^-\s+\*\*')


def _skip_frontmatter(lines):
    """Return lines with YAML frontmatter stripped (opening/closing ---)."""
    if not lines or lines[0].strip() != '---':
        return lines
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return lines[i + 1:]
    return lines  # unclosed frontmatter — return as-is


def audit_file(filepath):  # type: ignore[return]
    """
    Parse one critic-response file and return a list of (lineno, text) for
    each issue-bullet inside ## Issues / severity H3 that matched no Shape A–E.
    """
    with open(filepath, encoding='utf-8') as fh:
        raw_lines = fh.readlines()

    lines = _skip_frontmatter([ln.rstrip('\n') for ln in raw_lines])
    unrecognized = []
    in_issues_h2 = False
    in_severity_h3 = False

    for idx, line in enumerate(lines, start=1):
        # Track ## Issues H2 block
        if re.match(r'^##\s+Issues\s*$', line):
            in_issues_h2 = True
            in_severity_h3 = False
            continue
        if in_issues_h2 and _H2.match(line):
            # Another H2 ends the Issues block
            in_issues_h2 = False
            in_severity_h3 = False
            continue

        if not in_issues_h2:
            continue

        # Track severity H3 sub-sections
        if _ANY_H3.match(line):
            in_severity_h3 = bool(_SEVERITY_H3.match(line))
            continue

        if not in_severity_h3:
            continue

        # Only process top-level issue bullets (no leading indent)
        if not _TOP_BULLET.match(line):
            continue

        # It's a top-level bullet under a severity H3 — try each shape
        if not any(shape.match(line) for shape in SHAPES):
            unrecognized.append((idx, line))

    return unrecognized


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Audit bullet coverage of classify_critic_issues.py parser '
            'against the training corpus. Exits 0 if residual is empty, 1 if not.'
        )
    )
    default_training = os.path.join(
        os.path.dirname(__file__),
        'tests', 'fixtures', 'classify_critic_issues', 'training',
    )
    parser.add_argument(
        '--training-dir',
        default=default_training,
        help=f'Path to training fixture directory (default: {default_training})',
    )
    args = parser.parse_args()

    training_dir = args.training_dir
    if not os.path.isdir(training_dir):
        print(f'ERROR: training dir not found: {training_dir}', file=sys.stderr)
        sys.exit(2)

    fixture_files = sorted(
        os.path.join(training_dir, f)
        for f in os.listdir(training_dir)
        if f.endswith('.md') and f != 'README.md'
    )

    if not fixture_files:
        print('No fixture files found in training dir.', file=sys.stderr)
        sys.exit(0)

    total_unrecognized = 0
    for filepath in fixture_files:
        filename = os.path.basename(filepath)
        residuals = audit_file(filepath)
        for lineno, text in residuals:
            print(f'{filename}:{lineno}: {text}')
            total_unrecognized += 1

    sys.exit(1 if total_unrecognized > 0 else 0)


if __name__ == '__main__':
    main()
