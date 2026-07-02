/**
 * costSummaryParity.test.ts — cross-language parity test for parseCostSummary.
 *
 * Loads the shared JSON fixture from quoin/core/scripts/testdata/cost_summary_fixtures.json
 * (single source of truth with the Python test_cost_summary.py) and verifies that
 * parseCostSummary() produces results consistent with (expect_total, expect_partial).
 *
 * The fixture file is loaded via fs.readFileSync at a __dirname-relative path —
 * deliberately removing the file causes this test to fail at runtime.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { parseCostSummary } from '../costService';

// ---------------------------------------------------------------------------
// Load shared fixture at runtime (not a static import — validates path at load)
// ---------------------------------------------------------------------------

interface Fixture {
  name: string;
  summary: Record<string, unknown>;
  expect_total: number | null;
  expect_partial: boolean;
}

const FIXTURE_PATH = path.join(
  __dirname,
  '../../../quoin/core/scripts/testdata/cost_summary_fixtures.json',
);

let fixtures: Fixture[];
try {
  fixtures = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8')) as Fixture[];
} catch (err) {
  throw new Error(
    `Failed to load shared fixture at ${FIXTURE_PATH}: ${err}\n` +
    'Deliberately removing cost_summary_fixtures.json must cause this test to fail.',
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function expectedState(f: Fixture): 'unavailable' | 'partial' | 'live' {
  if (f.expect_total === null) { return 'unavailable'; }
  return f.expect_partial ? 'partial' : 'live';
}

// ---------------------------------------------------------------------------
// Parity tests — one per fixture entry
// ---------------------------------------------------------------------------

describe('costSummaryParity — parseCostSummary matches shared fixture', () => {
  for (const f of fixtures) {
    it(f.name, () => {
      const text = JSON.stringify(f.summary);
      const result = parseCostSummary(text, f.name);
      const expectedSt = expectedState(f);

      if (f.expect_total === null) {
        assert.strictEqual(
          result.finalizedUsd, null,
          `[${f.name}] expected finalizedUsd=null but got ${result.finalizedUsd}`,
        );
        assert.strictEqual(
          result.state, 'unavailable',
          `[${f.name}] expected state=unavailable but got ${result.state}`,
        );
      } else {
        assert.notStrictEqual(
          result.finalizedUsd, null,
          `[${f.name}] expected finalizedUsd=${f.expect_total} but got null`,
        );
        assert.ok(
          Math.abs(result.finalizedUsd! - f.expect_total) < 1e-9,
          `[${f.name}] expected finalizedUsd=${f.expect_total}, got ${result.finalizedUsd}`,
        );
        assert.strictEqual(
          result.state, expectedSt,
          `[${f.name}] expected state=${expectedSt} but got ${result.state}`,
        );
      }
    });
  }
});

// ---------------------------------------------------------------------------
// Fixture file integrity check
// ---------------------------------------------------------------------------

describe('costSummaryParity — fixture integrity', () => {
  it('fixture file is loadable and non-empty', () => {
    assert.ok(fixtures.length > 0, 'Fixture array must be non-empty');
  });

  it('fixture covers all 7 ladder keys', () => {
    const ladder = [
      'grand_total',
      'grand_total_usd',
      'total_usd',
      'total_cost_usd',
      'period_total_cost_usd',
      'estimated_task_cost_usd',
      'task_total',
    ];
    const allKeys = new Set<string>();
    for (const f of fixtures) {
      for (const k of Object.keys(f.summary)) {
        allKeys.add(k);
      }
    }
    for (const key of ladder) {
      assert.ok(
        allKeys.has(key),
        `Ladder key '${key}' not covered by any fixture case`,
      );
    }
  });
});
