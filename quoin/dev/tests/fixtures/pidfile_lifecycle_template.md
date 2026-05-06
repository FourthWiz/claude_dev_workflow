# §0c Pidfile lifecycle block template

## §0c Pidfile lifecycle (FIRST STEP after §0 dispatch)

At entry:
`{{ACQUIRE}}`

If acquire fails (e.g., script missing — fresh install before deploy):
emit one-line warning `[quoin-S-2: pidfile helpers unavailable; proceeding without lifecycle protection]`, continue without abort (fail-OPEN).

At exit:
`{{RELEASE}}`
