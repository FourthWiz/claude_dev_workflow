# Quoin Release Process

## Overview

Releases publish the `quoin` Python package to PyPI via GitHub Actions Trusted
Publishing triggered on a version tag push. No manual PyPI token management
is required.

## Bump version

The canonical version is stored in a single file:

```bash
sed -i.bak 's/__version__ = "X"/__version__ = "Y"/' src/quoin/__about__.py
rm src/quoin/__about__.py.bak
```

Never bump the version in two places — `pyproject.toml` reads the version
dynamically from `src/quoin/__about__.py` via hatchling `[tool.hatch.version]`.

## Hatchling pin

This project pins `hatchling>=1.18,<1.19` because hatchling 1.19 changed
`force-include` behavior in editable mode (issue #1130). The pin selects the
last known-good range. Re-evaluate the pin when issue #1130 is resolved.

## Release workflow

1. **Ensure main is clean** — all tests pass, no uncommitted changes.
2. **Bump version** — edit `src/quoin/__about__.py` (see above).
3. **Commit and tag:**
   ```bash
   git add src/quoin/__about__.py
   git commit -m "chore(release): bump version to vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```
4. **GitHub Actions triggers** — `.github/workflows/publish.yml` builds the
   wheel and sdist, runs `quoin --version` smoke check, then publishes to PyPI
   via Trusted Publishing.
5. **Verify on PyPI** — `pip install quoin==X.Y.Z` in a clean env, run
   `quoin install --help`.

## Initial registration (one-time manual step)

Before the first release, you must:
1. Create the project record at https://pypi.org/manage/projects/
2. Configure the Trusted Publisher: go to project → Publishing → Add publisher.
   Set `Owner: FourthWiz`, `Repository: quoin`, `Workflow: publish.yml`,
   `Environment: pypi`.

Token-based fallback: if Trusted Publishing is not available, create a PyPI
API token scoped to the `quoin` project and add it as a GitHub Actions secret
named `PYPI_API_TOKEN`. In `publish.yml`, replace the `id-token: write`
permission block with `password: ${{ secrets.PYPI_API_TOKEN }}`.

## Tests live in the git repo only

`quoin/dev/` is excluded from the sdist and the wheel. Tests require a git
clone to run. If a user installs via `pip install quoin`, they will not have
the test suite — this is intentional and documented here as an acknowledgment.

## Build verification (per PR)

Every PR runs a "build only" job in CI: builds the wheel, pip-installs it,
and runs `quoin --version` to catch packaging regressions before they reach
PyPI.
