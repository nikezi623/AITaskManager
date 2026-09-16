/**
 * Tests for docs/js/merge.js.
 *
 *   node tests/test_merge.mjs
 *
 * Two layers:
 *   1. Fixture cases from tests/merge_cases.json (shared with the future Python port).
 *   2. Randomized property tests over commutativity, associativity and idempotence.
 *      These cover far more ground than hand-written cases and are the real reason
 *      to trust the merge; a fixed PRNG seed keeps any failure reproducible.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import {
  SCHEMA, emptyState, normalizeState, mergeStates, mergeCell, pickRecord,
  applyCheckin, touchRecord, pruneTombstones, isChecked, checkedDates,
  liveRecords, stableStringify, nextStamp,
} from '../docs/js/merge.js';

const HERE = dirname(fileURLToPath(import.meta.url));

let passed = 0;
const failures = [];

function check(name, condition, detail) {
  if (condition) {
    passed++;
  } else {
    failures.push(detail ? `${name}\n    ${detail}` : name);
  }
}

function eq(name, actual, expected) {
  const a = stableStringify(actual);
  const b = stableStringify(expected);
  check(name, a === b, `expected ${b}\n    actual   ${a}`);
}

// ── 1. Fixture cases ─────────────────────────────────────────────────────

const fixtures = JSON.parse(readFileSync(join(HERE, 'merge_cases.json'), 'utf8'));

for (const c of fixtures.cases) {
  eq(`fixture: ${c.name}`, mergeStates(c.base, c.incoming), normalizeState(c.expected));
}

// ── 2. Structural guarantees ─────────────────────────────────────────────

const OUT_KEYS = ['schema', 'habits', 'groups', 'checkins', 'meta'];
{
  const out = mergeStates({ habits: { a: { id: 'a', updatedAt: 1, writer: 'x' } } }, {});
  eq('shape: merge output always has exactly the five top-level keys',
    Object.keys(out).sort(), [...OUT_KEYS].sort());
  check('shape: schema version is set on merge output', out.schema === SCHEMA);
  eq('shape: missing containers normalize to empty objects', normalizeState(null), emptyState());
  eq('shape: garbage normalizes to an empty state',
    normalizeState({ habits: 'nope', checkins: [1, 2], meta: 'x' }), emptyState());
}

// ── 3. Randomized property tests ─────────────────────────────────────────

/** mulberry32 -- small deterministic PRNG so failures reproduce. */
function rng(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Includes exact ties and both signs deliberately, to exercise the tie-break
// and sign-comparison paths rather than only the happy path.
const STAMPS = [500, 1000, 2000, 3000, -500, -1000, -2000, -3000];
const WRITERS = ['pc', 'phone', 'migrate'];
const DATES = ['2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17'];
const IDS = ['h1', 'h2', 'h3', 'g1', 'g2'];

function randomState(rand) {
  const pick = (arr) => arr[Math.floor(rand() * arr.length)];
  const state = emptyState();
  for (const id of IDS) {
    if (rand() < 0.6) {
      const table = id.startsWith('g') ? 'groups' : 'habits';
      state[table][id] = {
        id,
        name: `${table}-${id}-${Math.floor(rand() * 3)}`,
        order: Math.floor(rand() * 3) * 10,
        updatedAt: 1000 + Math.floor(rand() * 3) * 1000,
        writer: pick(WRITERS),
        deleted: rand() < 0.2,
      };
    }
  }
  for (const id of ['h1', 'h2', 'h3']) {
    if (rand() < 0.75) {
      const cells = {};
      for (const date of DATES) {
        if (rand() < 0.5) cells[date] = pick(STAMPS);
      }
      state.checkins[id] = cells;
    }
  }
  if (rand() < 0.5) {
    state.meta = { bot_enabled: rand() < 0.5, updatedAt: 1000 + Math.floor(rand() * 3) * 1000, writer: pick(WRITERS) };
  }
  return state;
}

const ROUNDS = 4000;
let violations = 0;
let assocViolations = 0;

for (let i = 0; i < ROUNDS; i++) {
  const rand = rng(0x9e3779b9 ^ i);
  const a = randomState(rand);
  const b = randomState(rand);
  const c = randomState(rand);

  // Idempotence: merge(a, a) === a
  if (stableStringify(mergeStates(a, a)) !== stableStringify(normalizeState(a))) {
    violations++;
    if (violations <= 2) console.error(`idempotence failed on round ${i}`);
  }

  // Commutativity: merge(a, b) === merge(b, a)
  if (stableStringify(mergeStates(a, b)) !== stableStringify(mergeStates(b, a))) {
    violations++;
    if (violations <= 2) console.error(`commutativity failed on round ${i}`);
  }

  // Associativity: merge(merge(a,b),c) === merge(a,merge(b,c))
  if (stableStringify(mergeStates(mergeStates(a, b), c)) !==
      stableStringify(mergeStates(a, mergeStates(b, c)))) {
    assocViolations++;
    if (assocViolations <= 2) console.error(`associativity failed on round ${i}`);
  }
}

check(`property: ${ROUNDS} rounds of idempotence + commutativity`, violations === 0,
  `${violations} violations`);
check(`property: ${ROUNDS} rounds of associativity`, assocViolations === 0,
  `${assocViolations} violations`);

// Convergence: merging in any order yields the same state, so a retry after a
// 409 can never produce a different result than a first attempt.
{
  const rand = rng(42);
  const a = randomState(rand);
  const b = randomState(rand);
  const c = randomState(rand);
  const orders = [
    [a, b, c], [c, b, a], [b, a, c], [b, c, a],
  ].map((order) => order.reduce((acc, s) => mergeStates(acc, s)));
  const first = stableStringify(orders[0]);
  check('property: merge is order-independent across three devices',
    orders.every((o) => stableStringify(o) === first));
}

// ── 4. Mutation helpers own invariant I1 ─────────────────────────────────

{
  const state = emptyState();
  // Repeated writes in the same second must still produce increasing stamps,
  // otherwise two different versions of a record could tie and pickRecord
  // would fall back to comparing content.
  applyCheckin(state, 'h1', '2026-09-14', true, 1000);
  const first = state.checkins.h1['2026-09-14'];
  applyCheckin(state, 'h1', '2026-09-14', false, 1000);
  const second = state.checkins.h1['2026-09-14'];
  applyCheckin(state, 'h1', '2026-09-14', true, 1000);
  const third = state.checkins.h1['2026-09-14'];

  check('I1: stamps strictly increase under same-second rewrites',
    first < Math.abs(second) && Math.abs(second) < third,
    `got ${first}, ${second}, ${third}`);
  check('I1: sign encodes the requested state', first > 0 && second < 0 && third > 0);
  check('I1: a later stamp beats an earlier one', mergeCell(second, third) === third);

  check('nextStamp: never goes backwards even with a clock in the past',
    nextStamp(5000, 100) === 5001, `got ${nextStamp(5000, 100)}`);

  const rec = { id: 'h1', updatedAt: 9000, writer: 'pc' };
  touchRecord(rec, 100, 'phone');
  check('I1: touchRecord bumps past an existing future stamp',
    rec.updatedAt === 9001 && rec.writer === 'phone', JSON.stringify(rec));

  // A device with a wrong clock must not be able to permanently win.
  const stale = { updatedAt: 1e15, writer: 'phone' };
  const fresh = { updatedAt: 9001, writer: 'pc' };
  check('pickRecord: higher stamp wins regardless of writer',
    pickRecord(stale, fresh) === stale);
}

// ── 5. Read helpers ──────────────────────────────────────────────────────

{
  const state = emptyState();
  applyCheckin(state, 'h1', '2026-09-14', true, 1000);
  applyCheckin(state, 'h1', '2026-09-15', false, 2000);
  applyCheckin(state, 'h1', '2026-09-16', true, 3000);

  check('isChecked: a tombstone reads as unchecked', !isChecked(state, 'h1', '2026-09-15'));
  check('isChecked: a positive cell reads as checked', isChecked(state, 'h1', '2026-09-16'));
  check('isChecked: a missing cell reads as unchecked', !isChecked(state, 'h1', '2026-09-17'));
  check('isChecked: an unknown habit reads as unchecked', !isChecked(state, 'nope', '2026-09-16'));
  eq('checkedDates: excludes tombstones',
    checkedDates(state, 'h1').sort(), ['2026-09-14', '2026-09-16']);
}

{
  const habits = {
    a: { id: 'a', deleted: false },
    b: { id: 'b', deleted: true },
    c: { id: 'c' },
  };
  eq('liveRecords: drops tombstones', liveRecords(habits).map((h) => h.id), ['a', 'c']);
  eq('liveRecords: tolerates null', liveRecords(null), []);
}

// ── 6. Tombstone pruning ─────────────────────────────────────────────────

{
  const now = 1_760_000_000; // must be a realistic epoch: nextStamp clamps to
  const day = 86400;         // max(nowSec, ...), so tiny values skew the math
  const state = emptyState();
  applyCheckin(state, 'h1', 'old-tombstone', false, now - 200 * day);
  applyCheckin(state, 'h1', 'recent-tombstone', false, now - 10 * day);
  applyCheckin(state, 'h1', 'ancient-checkin', true, now - 400 * day);

  pruneTombstones(state, now, 180);

  check('prune: aged tombstone is dropped', state.checkins.h1['old-tombstone'] === undefined);
  check('prune: recent tombstone is kept', state.checkins.h1['recent-tombstone'] !== undefined);
  check('prune: a real check-in is never dropped, however old',
    state.checkins.h1['ancient-checkin'] !== undefined);
}

// ── 7. stableStringify ───────────────────────────────────────────────────

{
  eq('stableStringify: key order does not matter',
    stableStringify({ b: 1, a: 2 }), stableStringify({ a: 2, b: 1 }));
  check('stableStringify: distinguishes different values',
    stableStringify({ a: 1 }) !== stableStringify({ a: 2 }));
  eq('stableStringify: handles nested objects and arrays',
    stableStringify({ z: [{ b: 1, a: 2 }], a: null }),
    '{"a":null,"z":[{"a":2,"b":1}]}');
  eq('stableStringify: undefined becomes null, matching JSON',
    stableStringify({ a: undefined }), '{}');
}

// ── Report ───────────────────────────────────────────────────────────────

const total = passed + failures.length;
if (failures.length) {
  console.error(`\n${failures.length} of ${total} checks FAILED:\n`);
  for (const f of failures) console.error(`  ✗ ${f}`);
  process.exit(1);
}
console.log(`✓ all ${total} checks passed (${fixtures.cases.length} fixtures, ${ROUNDS * 3} property rounds)`);
