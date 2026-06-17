This fixture exercises V-05 selectivity after IVG-78.

Case 1 — backtick-quoted undefined ID (exempt, must NOT appear in FAIL output):
The sibling plan's `T-88` is in backtick form; no local definition exists for it.

Case 2 — bare undefined ID (must still produce FAIL):
T-97

Case 3 — adjacent unrelated backtick span on same line as bare undefined ID:
`some_function()` T-96
