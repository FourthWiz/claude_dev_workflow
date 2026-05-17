"""
pick_subset.py — Deterministic subset selector for quoin benchmark suite v1.

Reads the upstream EvalPlus HumanEval+ manifest and SWE-bench Lite manifest,
applies a seeded shuffle, and writes suite-v1.json with the selected subset.

Usage:
    python3 quoin/benchmarks/scripts/pick_subset.py --seed 1729

Output is byte-for-byte reproducible from the same seed and the same upstream
manifests. If the upstream manifests change (new problems added, IDs renumbered),
re-run with the same seed; compare output SHA against the previous suite-v1.json
to detect any drift.

The script writes output to stdout (JSON) by default, or to --output if given.
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Upstream manifest stubs
# When running live against the actual evalplus / swebench packages, replace
# these stubs with real data loader calls:
#   from evalplus.data import get_human_eval_plus
#   from swebench.harness.utils import load_swebench_dataset
# For the v1 deterministic suite the actual list of IDs is fixed here to
# guarantee byte-for-byte reproducibility without network access.
# ---------------------------------------------------------------------------

HUMANEVAL_PLUS_IDS = [f"HumanEval/{i}" for i in range(164)]

SWEBENCH_LITE_PROBLEM_IDS = [
    "astropy__astropy-12907",
    "astropy__astropy-13033",
    "astropy__astropy-13236",
    "astropy__astropy-13390",
    "astropy__astropy-14096",
    "astropy__astropy-14182",
    "astropy__astropy-14309",
    "astropy__astropy-14365",
    "astropy__astropy-6938",
    "astropy__astropy-7746",
    "django__django-10097",
    "django__django-10606",
    "django__django-10924",
    "django__django-11019",
    "django__django-11099",
    "django__django-11133",
    "django__django-11422",
    "django__django-11564",
    "django__django-11742",
    "django__django-11815",
    "django__django-11999",
    "django__django-12286",
    "django__django-12453",
    "matplotlib__matplotlib-18869",
    "matplotlib__matplotlib-23299",
    "psf__requests-2317",
    "psf__requests-3362",
    "pylint-dev__pylint-5859",
    "pydata__xarray-4094",
    "scikit-learn__scikit-learn-10508",
    "scikit-learn__scikit-learn-13142",
    "sphinx-doc__sphinx-8627",
    "sympy__sympy-14396",
    "sympy__sympy-15346",
    "sympy__sympy-15670",
    "sympy__sympy-16503",
    "sympy__sympy-17022",
    "sympy__sympy-17139",
    "sympy__sympy-17630",
    "sympy__sympy-18087",
]

DIFFICULTY_BANDS = {
    "easy": list(range(0, 30)),
    "medium": list(range(30, 100)),
    "hard": list(range(100, 164)),
}

EXPECTED_MINUTES_BY_DIFFICULTY = {
    "easy": 3,
    "medium": 5,
    "hard": 8,
}


def classify_difficulty(idx: int) -> str:
    if idx < 30:
        return "easy"
    if idx < 100:
        return "medium"
    return "hard"


def pick_humaneval_plus(n: int, seed: int) -> list[dict]:
    """Select n HumanEval+ tasks reproducibly from the full set."""
    rng = random.Random(seed)
    sorted_ids = sorted(HUMANEVAL_PLUS_IDS)
    shuffled = list(sorted_ids)
    rng.shuffle(shuffled)
    selected = shuffled[:n]
    # Sort selected by numeric ID for stable output order
    selected.sort(key=lambda x: int(x.split("/")[1]))

    tasks = []
    for rank, source_id in enumerate(selected):
        idx = int(source_id.split("/")[1])
        difficulty = classify_difficulty(idx)
        tasks.append(
            {
                "id": f"humaneval_plus_{rank:03d}",
                "source": "evalplus_humaneval_plus",
                "source_id": source_id,
                "difficulty_band": difficulty,
                "deterministic_seed": seed,
                "expected_minutes_p50": EXPECTED_MINUTES_BY_DIFFICULTY[difficulty],
            }
        )
    return tasks


def pick_swebench_lite(n: int, seed: int) -> list[dict]:
    """Select n SWE-bench Lite tasks reproducibly."""
    rng = random.Random(seed + 1)  # distinct sub-seed for each benchmark
    sorted_ids = sorted(SWEBENCH_LITE_PROBLEM_IDS)
    shuffled = list(sorted_ids)
    rng.shuffle(shuffled)
    selected = shuffled[:n]
    selected.sort()

    tasks = []
    for rank, source_id in enumerate(selected):
        tasks.append(
            {
                "id": f"swebench_lite_{rank:03d}",
                "source": "swebench_lite",
                "source_id": source_id,
                "difficulty_band": "hard",
                "deterministic_seed": seed,
                "expected_minutes_p50": 15,
            }
        )
    return tasks


def build_suite(
    n_humaneval: int,
    n_swebench: int,
    seed: int,
) -> dict:
    humaneval_tasks = pick_humaneval_plus(n_humaneval, seed)
    swebench_tasks = pick_swebench_lite(n_swebench, seed)
    tasks = humaneval_tasks + swebench_tasks

    suite = {
        "schema_version": 2,
        "description": (
            f"Quoin benchmark v1 task suite — {n_humaneval} EvalPlus HumanEval+ tasks"
            f" + {n_swebench} SWE-bench Lite instances."
            f" Generated deterministically via pick_subset.py --seed {seed}."
            " Do not edit manually; regenerate from pick_subset.py."
        ),
        "generated_by": "quoin/benchmarks/scripts/pick_subset.py",
        "seed": seed,
        "provenance_file": "quoin/benchmarks/suite-v1-provenance.md",
        "tasks": tasks,
    }
    return suite


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic quoin benchmark suite-v1.json"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1729,
        help="Random seed for deterministic shuffle (default: 1729)",
    )
    parser.add_argument(
        "--n-humaneval",
        type=int,
        default=100,
        help="Number of HumanEval+ tasks to select (default: 100)",
    )
    parser.add_argument(
        "--n-swebench",
        type=int,
        default=20,
        help="Number of SWE-bench Lite tasks to select (default: 20)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: stdout)",
    )
    parser.add_argument(
        "--verify",
        type=Path,
        default=None,
        help="Verify that --output matches an existing file byte-for-byte",
    )
    args = parser.parse_args()

    suite = build_suite(args.n_humaneval, args.n_swebench, args.seed)
    output_json = json.dumps(suite, indent=2, ensure_ascii=False) + "\n"

    if args.verify:
        existing = args.verify.read_text(encoding="utf-8")
        if existing == output_json:
            print(f"VERIFY OK: {args.verify} matches generated output (seed={args.seed})")
            sys.exit(0)
        else:
            print(
                f"VERIFY FAIL: {args.verify} does not match generated output",
                file=sys.stderr,
            )
            existing_hash = hashlib.sha256(existing.encode()).hexdigest()[:12]
            new_hash = hashlib.sha256(output_json.encode()).hexdigest()[:12]
            print(f"  existing sha256[:12] = {existing_hash}", file=sys.stderr)
            print(f"  generated sha256[:12] = {new_hash}", file=sys.stderr)
            sys.exit(1)

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
        sha = hashlib.sha256(output_json.encode()).hexdigest()
        print(f"Written to {args.output} (sha256={sha})")
    else:
        sys.stdout.write(output_json)


if __name__ == "__main__":
    main()
