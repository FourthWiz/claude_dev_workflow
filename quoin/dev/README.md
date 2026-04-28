# quoin/dev/

This folder holds dev-only artifacts for quoin maintainers: the test suite (`tests/`),
test fixtures (`tests/fixtures/`), the measurement utility (`measure_v3_savings.py`),
and manual verification documents (`verify_subagent_dispatch.md`,
`verify_path_resolve_smoke.md`).

**These files are NOT deployed by `install.sh` and are not part of the end-user install.**
End users running `bash install.sh` will never see this folder's contents in `~/.claude/`.

Maintainers can run the test suite after installing dev dependencies:

```
bash install.sh --dev
pytest quoin/dev/tests/
```

Do NOT reference paths under `quoin/dev/` from runtime skills or from the `## Working Rules`
sections of CLAUDE.md — those sections are deployed to end-user machines where this folder
does not exist.
