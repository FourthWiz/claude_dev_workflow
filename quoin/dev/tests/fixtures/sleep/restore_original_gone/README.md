Expected: --restore redirects to daily/insights-<today>.md with Restored prefix.

The forgotten/2026-03-10.md file contains one block with a > Source: anchor pointing to
/nonexistent/path/that/does/not/exist/insights-2026-02-15.md — a path that does NOT exist.

The --restore path should:
1. Read the Source: anchor
2. Find the original file does not exist (precedence 1 fails)
3. Redirect to today's insights file with "> Restored from forgotten/2026-03-10.md" prefix (precedence 2)
4. Confirm with user before appending
