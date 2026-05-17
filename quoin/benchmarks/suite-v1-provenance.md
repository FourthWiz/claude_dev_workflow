# Suite v1 Provenance

## Dataset versions

| Dataset | Version | Pinned commit / release |
|---|---|---|
| EvalPlus HumanEval+ | evalplus 0.3.0 | Pin at run time via `python3 -c "import evalplus; print(evalplus.__version__)"` |
| SWE-bench Lite | swebench 3.0.0 | Pin at run time via `python3 -c "import swebench; print(swebench.__version__)"` |

## Subset selection

- Tool: `quoin/benchmarks/scripts/pick_subset.py`
- Seed: 1729 (Ramanujan's taxicab number — chosen for memorability and
  reproducibility; not chosen by examining results)
- HumanEval+ problems: first 100 after seeded shuffle of all 164 IDs, sorted
  by numeric ID for stable output order
- SWE-bench Lite instances: first 20 after seeded shuffle (sub-seed = 1730),
  sorted by ID

## Reproducing the suite

```bash
python3 quoin/benchmarks/scripts/pick_subset.py --seed 1729 \
  --n-humaneval 100 --n-swebench 20 \
  --output /tmp/suite-v1-reproduced.json

# Verify byte-for-byte match (after updating IDs to match actual upstream manifests)
python3 quoin/benchmarks/scripts/pick_subset.py --seed 1729 \
  --n-humaneval 100 --n-swebench 20 \
  --verify quoin/benchmarks/suite-v1.json
```

## Contamination surface (explicitly accepted)

The following contamination vectors are accepted and documented:

1. **Model training data:** Both Claude and Codex were trained on data that
   likely includes HumanEval problems and their solutions. We do not attempt to
   control for this; it is a universal limitation of current LLM benchmarking.
2. **EvalPlus augmentation:** EvalPlus extends HumanEval with more test cases,
   but the function prompts themselves are unchanged. Training contamination
   risk is the same as for plain HumanEval.
3. **SWE-bench Lite public availability:** All SWE-bench Lite instances are
   publicly available on GitHub; training data may include solutions to some.
4. **Toolkit code itself:** Both quoin-claude and quoin-codex cells use quoin
   code from the repo that was potentially in training data. This is by design —
   quoin is the system under test.
5. **Agent system prompt:** The Claude Code and Codex system prompts may have
   evolved between training time and benchmark time. We pin dated model snapshots
   (per invariant 1) to minimize drift.

We do NOT attempt to control for training data contamination in v1. The primary
conclusion is rank-order stability (does quoin consistently help on tasks where
the agent would otherwise fail), not absolute pass-rate comparison with other
published benchmarks.
