#!/usr/bin/env python3
"""
summarize_for_human.py — Haiku-powered ## For human summary generator.

Stage 1 deliverable of artifact-format-architecture v3 (see architecture §5.3.1).
Calls the Anthropic Haiku model to produce a 5-8 line plain-English summary
of a Class B artifact body, suitable for prepending as the ## For human section.

The prompt template is FROZEN for Stage 1. Changes require a Stage 4 re-pass
per architecture §5.3.1 governance (the prompt is a contract between skills).

CLI contract:
  Usage: summarize_for_human.py <body-file-path>
  Stdin: (none)
  Stdout: 5-8 line summary text (newline-separated)
  Stderr: error messages on failure
  Exit:  0 = success, non-zero = failure
  Env:   ANTHROPIC_API_KEY required

Dependency note: `anthropic` SDK is lazy-imported inside _call_haiku() so that
argparse, --help, missing-API-key, and missing-body-file paths all run without
the SDK installed (MAJ-3 lazy-import resolution).
"""

import argparse
import os
import sys

# Model pinned at script-update time, not at runtime (per architecture §5.3.1).
# Update this constant when the model identifier is retired.
MODEL = "claude-haiku-4-5-20251001"

# Prompt template frozen for Stage 1 (architecture §5.3.1).
# Constraint: do NOT invent facts not present in the body.
PROMPT_TEMPLATE = (
    "You are summarizing a workflow artifact for a human reader who will skim, "
    "not read end-to-end.\n"
    "Produce a `## For human` summary covering, in 5-8 lines of plain English:\n"
    "1. Current status (one line).\n"
    "2. Biggest open risk or blocker (one line).\n"
    "3. What's needed to make progress (one line).\n"
    "4. What comes next (one line).\n"
    "Constraints: do NOT invent facts not present in the body. "
    "Do NOT use compressed/terse syntax. Do NOT exceed 8 lines.\n"
    "Body to summarize:\n"
    "<<<BODY>>>"
)

TIMEOUT_SECONDS = 30
MAX_TOKENS = 400


def _call_haiku(body_text, api_key):
    """Call Haiku and return the summary text. anthropic is lazy-imported here."""
    try:
        import anthropic  # lazy import — SDK optional for non-API paths
    except ModuleNotFoundError:
        print(
            "anthropic SDK not installed — run: pip install anthropic",
            file=sys.stderr,
        )
        sys.exit(1)

    prompt = PROMPT_TEMPLATE.replace("<<<BODY>>>", body_text)

    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=float(TIMEOUT_SECONDS))
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except anthropic.APIError as e:
        print(f"Haiku call failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Haiku call failed: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a ## For human summary for a Class B dev-workflow artifact body."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Usage: summarize_for_human.py <body-file-path>\n"
            "Requires: ANTHROPIC_API_KEY environment variable\n"
            "Model: " + MODEL + " (pinned at script-update time)\n"
        ),
    )
    parser.add_argument(
        "body_file",
        metavar="body-file-path",
        help="Path to the artifact body file to summarize",
    )
    args = parser.parse_args()

    # Check body file exists (before API key check — argparse errors first)
    if not os.path.isfile(args.body_file):
        print(
            f"summarize_for_human.py: body file not found: {args.body_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check API key (before lazy import of anthropic)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ANTHROPIC_API_KEY missing — set it in your shell to enable v3 Class B summary blocks; "
            "v2-format fallback is being used",
            file=sys.stderr,
        )
        sys.exit(1)

    # Read body
    try:
        with open(args.body_file, encoding="utf-8") as f:
            body_text = f.read()
    except OSError as e:
        print(f"summarize_for_human.py: cannot read body file: {e}", file=sys.stderr)
        sys.exit(1)

    # Call Haiku (lazy import of anthropic happens inside _call_haiku)
    summary = _call_haiku(body_text, api_key)
    print(summary)


if __name__ == "__main__":
    main()
