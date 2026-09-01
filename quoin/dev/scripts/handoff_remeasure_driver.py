#!/usr/bin/env python3
# CLAUDE-ADAPTER-OWNED — reconstruction of the ad-hoc importer stage 4 used to
# drive `handoff-remeasure.md` (see that report's own "Methodology note
# (MIN-11)"). Stage 4's version was never committed; this is stage 5's T-09
# fix for that gap, so a future stage is not in the same position. Uses only
# public functions from `handoff_measure.py`, called directly rather than
# through a new CLI surface (MIN-11's own preference). No test suite
# discovers this file; it is a one-off report-generation aid, mirroring
# quoin/dev/scripts/census_descriptions.py.
#
# Per D-12, every `contract_reads_in_spawn`/`contract_read_partition` call
# below passes an explicit single-element `contract_names` tuple — never a
# bare call — so the core and reference read rates are never silently
# blended into one union rate.

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import handoff_measure as hm  # noqa: E402


def main():
    home = str(Path.home())
    corpus = hm.capture_corpus(home)
    print(f"transcripts={corpus['transcripts']} parsed={corpus['parsed']} "
          f"skipped_unreadable={corpus['skipped_unreadable']}")
    print(f"legacy_run_owned={corpus['run_owned']}")

    records = corpus["records"]
    legacy_run_owned = [r for r in records if r.get("run_owned")]
    envelope_run_owned = [
        r for r in records
        if hm.envelope_phase(r.get("dispatch_text", "")) in hm.RUN_OWNED_PHASES
    ]
    print(f"envelope_run_owned={len(envelope_run_owned)}")

    legacy_ids = {id(r) for r in legacy_run_owned}
    envelope_ids = {id(r) for r in envelope_run_owned}
    both = len(legacy_ids & envelope_ids)
    print(f"cross_tab both={both} legacy_only={len(legacy_ids) - both} "
          f"envelope_only={len(envelope_ids) - both} "
          f"neither={corpus['parsed'] - len(legacy_ids | envelope_ids)}")

    post_population = envelope_run_owned
    n = len(post_population)
    print(f"post_population_n={n}")
    if n:
        per_phase = {}
        on_behalf = 0
        for r in post_population:
            phase = hm.envelope_phase(r.get("dispatch_text", ""))
            per_phase[phase] = per_phase.get(phase, 0) + 1
            if hm.sentinel_bucket(r.get("dispatch_text", "")) == "on_behalf":
                on_behalf += 1
        print(f"per_phase={per_phase} on_behalf={on_behalf}")

        stats = hm.channel_stats(post_population)
        print(f"dispatch_stats={json.dumps(stats.get('dispatch'), default=str)}")
        print(f"return_stats={json.dumps(stats.get('return'), default=str)}")

        ep = hm.envelope_partition(records)
        print(f"envelope_partition_full: n={ep['n']} "
              f"dispatch_envelope_count={ep['dispatch_envelope_count']} "
              f"return_envelope_count={ep['return_envelope_count']}")

        crp_core = hm.contract_read_partition(post_population, ("handoff-format.md",))
        print(f"contract_read_core: n={crp_core['n']} hits={crp_core['hits']} "
              f"fraction={crp_core['fraction']}")
        crp_ref = hm.contract_read_partition(post_population, ("handoff-format-reference.md",))
        print(f"contract_read_reference: n={crp_ref['n']} hits={crp_ref['hits']} "
              f"fraction={crp_ref['fraction']}")

        project_root = str(Path(__file__).resolve().parents[3])
        gb = hm.growth_bound(post_population, home, project_root)
        print(f"growth_bound: n_spawns={gb['n_spawns']} n_sessions={gb['n_sessions']} "
              f"extraction_coverage={gb['extraction_coverage']} "
              f"whole_per_run={gb.get('whole_per_run')} "
              f"per_candidate_per_run={gb.get('per_candidate_per_run')}")

        sessions_seen = set()
        session_results = []
        run_owned_tool_use_ids = None
        for r in post_population:
            parent = hm.resolve_parent_transcript_path(r["path"])
            if parent is None or parent in sessions_seen:
                continue
            sessions_seen.add(parent)
            session_results.append(hm.channel_three_for_session(parent, run_owned_tool_use_ids))
        if session_results:
            c3 = hm.channel_three_stats(session_results)
            print(f"channel_three: sub_a_bytes={c3['sub_a_bytes']} "
                  f"sub_b_bytes={c3['sub_b_bytes']} byte_share_3a={c3['byte_share_3a']}")
        else:
            print("channel_three: no resolvable parent sessions")
    else:
        print("post_population empty; channel one/two/three and contract-read "
              "sections are UNMEASURED this run")


if __name__ == "__main__":
    main()
