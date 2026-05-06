# Pip Install Migration — Manual Smoke Checklist

Mirrors `quoin/dev/verify_subagent_dispatch.md` pattern. Hand-fill each step.

## Scenario A — Existing install.sh user re-runs from updated source

User has a prior `bash install.sh` deployment. They `git pull` to get the new
version and re-run.

```bash
git pull
bash quoin/install.sh
```

Expected:
- [ ] Exit 0
- [ ] stdout contains `Updated quoin section in ~/.claude/CLAUDE.md`
- [ ] `quoin doctor` exits 0
- [ ] No new duplicate marker pairs in `~/.claude/CLAUDE.md`

`quoin doctor` output: _(paste here)_

## Scenario B — Fresh pip install + quoin install

User installs for the first time via pip.

```bash
pip install quoin
quoin install
```

Expected:
- [ ] `pip install quoin` exits 0, `quoin --version` prints `quoin X.Y.Z`
- [ ] `quoin install` exits 0, same outcome as `bash install.sh`
- [ ] `quoin doctor` exits 0 with all checks green
- [ ] `~/.claude/CLAUDE.md` has exactly 1 marker section

`quoin doctor` output: _(paste here)_

## Scenario C — Editable install + quoin install (from git clone)

User clones the repo and uses the editable path.

```bash
git clone https://github.com/FourthWiz/quoin
cd quoin
pip install -e .
quoin install
```

Expected:
- [ ] `pip install -e .` exits 0
- [ ] `quoin install` exits 0 (resolver takes editable-install branch, not Tier 1 importlib)
- [ ] Preambles regenerated (working-tree write allowed via allow_writes=True)
- [ ] `quoin doctor` exits 0

`quoin doctor` output: _(paste here)_

## Scenario D — Multi-marker recovery path

Verifies the `--force-merge` recovery flag (MAJ-2 round-3).

Seed `~/.claude/CLAUDE.md` with two marker pairs, then:

```bash
quoin install
```

Expected:
- [ ] Exit 2 with error: `quoin: ~/.claude/CLAUDE.md contains 2 '# === DEV WORKFLOW' marker pairs`
- [ ] Error message mentions `quoin install --force-merge` as recovery hint

Then run:

```bash
quoin install --force-merge
```

Expected:
- [ ] Exit 0
- [ ] stderr contains `quoin: removed extra '# === DEV WORKFLOW' marker pair at line N`
- [ ] `~/.claude/CLAUDE.md` has exactly 1 marker pair
- [ ] `quoin doctor` exits 0

Result: _(pass/fail + notes)_
