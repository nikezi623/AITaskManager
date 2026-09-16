/**
 * Conflict-free merge for ATM habit data.
 *
 * This file is the single source of truth for the merge. A future Python port
 * (for the desktop app) must pass the same fixtures in tests/merge_cases.json.
 *
 * Every exported function here is pure: no I/O, no Date.now(), no globals.
 * Callers pass the current time in explicitly.
 *
 * ── The model ────────────────────────────────────────────────────────────
 * Check-ins merge per cell (habit x date) with a last-write-wins register;
 * habits and groups merge per record. Cell values are sign-encoded:
 *
 *     v > 0   checked at epoch-second v
 *     v < 0   explicitly unchecked at epoch-second -v   ("tombstone")
 *
 * The tombstone is a *value*, not an event -- it is never consumed by a merge,
 * so it keeps winning on every device forever. That is what makes un-checking
 * propagate correctly to a device that still believes the day was checked.
 *
 * ── Two invariants the caller MUST uphold (see nextStamp/touchRecord) ────
 * I1. Timestamps are strictly monotonic per cell/record.
 * I2. Records are always written whole, never partially.
 *
 * I1 is what lets pickRecord() ignore content entirely. Comparing record
 * contents across JS and Python is a genuine divergence trap (number formats,
 * unicode escaping, key order), so the design avoids needing to.
 */

export const SCHEMA = 3;

/** Tombstones older than this are dropped; a real check-in never is. */
export const TOMBSTONE_TTL_DAYS = 180;

export function emptyState() {
  return { schema: SCHEMA, habits: {}, groups: {}, checkins: {}, meta: null };
}

/** Coerce anything (parsed JSON, corrupted storage) into a usable state. */
export function normalizeState(raw) {
  const s = raw && typeof raw === 'object' ? raw : {};
  const obj = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v : {});
  return {
    schema: SCHEMA,
    habits: obj(s.habits),
    groups: obj(s.groups),
    checkins: obj(s.checkins),
    meta: s.meta && typeof s.meta === 'object' ? s.meta : null,
  };
}

// ── Merge primitives ─────────────────────────────────────────────────────

/**
 * Merge one (habit, date) cell.
 *
 * Note this compares MAGNITUDES first and only then applies the sign. A plain
 * `Math.max(a, b)` would let an old check-in (+1000) beat a newer un-check
 * (-5000) and silently resurrect a day the user deliberately cleared.
 */
export function mergeCell(a, b) {
  if (a == null) return b;
  if (b == null) return a;
  const aa = Math.abs(a);
  const ab = Math.abs(b);
  if (aa !== ab) return aa > ab ? a : b; // newer timestamp wins
  return Math.max(a, b); // exact tie: checked beats unchecked
}

/**
 * Merge one habit/group/meta record.
 *
 * A total order over *arbitrary* record pairs, not just ones reachable through
 * the mutation helpers. The first two comparators do the real work; the third
 * is defense in depth. If (updatedAt, writer) ever ties, invariant I1 was
 * violated -- a bug elsewhere, or hand-edited JSON -- and falling back to
 * "whichever came first" would let each device keep a different version and
 * silently disagree forever. Comparing content keeps the result deterministic
 * even then.
 */
export function pickRecord(a, b) {
  if (!a) return b;
  if (!b) return a;
  if (a.updatedAt !== b.updatedAt) return a.updatedAt > b.updatedAt ? a : b;
  if (a.writer !== b.writer) return a.writer < b.writer ? a : b;
  return stableStringify(a) <= stableStringify(b) ? a : b;
}

/**
 * Merge two full states. Commutative, associative and idempotent -- which is
 * what makes retries free and "lost update" impossible by construction rather
 * than by luck.
 */
export function mergeStates(base, incoming) {
  const a = normalizeState(base);
  const b = normalizeState(incoming);
  const out = emptyState();

  for (const table of ['habits', 'groups']) {
    for (const id of new Set([...Object.keys(a[table]), ...Object.keys(b[table])])) {
      out[table][id] = pickRecord(a[table][id], b[table][id]);
    }
  }

  for (const habitId of new Set([...Object.keys(a.checkins), ...Object.keys(b.checkins)])) {
    const left = a.checkins[habitId] || {};
    const right = b.checkins[habitId] || {};
    const cells = {};
    for (const date of new Set([...Object.keys(left), ...Object.keys(right)])) {
      cells[date] = mergeCell(left[date], right[date]);
    }
    out.checkins[habitId] = cells;
  }

  out.meta = pickRecord(a.meta, b.meta) || null;
  return out;
}

// ── Mutation helpers (these own the monotonic invariant I1) ──────────────

/** Next stamp for a value: never decreases, never repeats. */
export function nextStamp(prev, nowSec) {
  return Math.max(Math.floor(nowSec), Math.abs(prev || 0) + 1);
}

/** Toggle or set a check-in, maintaining I1. Mutates `state`, returns it. */
export function applyCheckin(state, habitId, date, checked, nowSec) {
  const cells = (state.checkins[habitId] ||= {});
  const mag = nextStamp(cells[date], nowSec);
  cells[date] = checked ? mag : -mag;
  return state;
}

/** Bump a record's updatedAt before writing it whole (I2). Mutates `rec`. */
export function touchRecord(rec, nowSec, writer) {
  rec.updatedAt = nextStamp(rec.updatedAt, nowSec);
  rec.writer = writer;
  return rec;
}

/** Drop aged tombstones so cancelled days don't accumulate forever. */
export function pruneTombstones(state, nowSec, ttlDays = TOMBSTONE_TTL_DAYS) {
  const cutoff = nowSec - ttlDays * 86400;
  for (const cells of Object.values(state.checkins)) {
    for (const [date, value] of Object.entries(cells)) {
      if (value < 0 && -value < cutoff) delete cells[date];
    }
  }
  return state;
}

// ── Read helpers ─────────────────────────────────────────────────────────

/** Effective checked state of one cell: only a positive value means checked. */
export function isChecked(state, habitId, date) {
  const v = state.checkins?.[habitId]?.[date];
  return typeof v === 'number' && v > 0;
}

/** All dates with an effective check-in for a habit, unsorted. */
export function checkedDates(state, habitId) {
  const cells = state.checkins?.[habitId] || {};
  return Object.keys(cells).filter((d) => cells[d] > 0);
}

/** Records that still exist (tombstones filtered out). */
export function liveRecords(table) {
  return Object.values(table || {}).filter((r) => r && !r.deleted);
}

/**
 * Key-sorted stringify. Used only for equality fast-paths and commit messages
 * -- never for a merge decision -- but it must be stable across reloads, and
 * insertion order is not.
 */
export function stableStringify(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return '[' + value.map(stableStringify).join(',') + ']';
  const keys = Object.keys(value).filter((k) => value[k] !== undefined).sort();
  return '{' + keys.map((k) => JSON.stringify(k) + ':' + stableStringify(value[k])).join(',') + '}';
}
