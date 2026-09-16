/**
 * Tests for docs/js/store.js.
 *
 *   node tests/test_store.mjs
 *
 * store.js is where the real logic bugs hide -- ordering, streaks, the weekly
 * denominator, delete cascades -- and none of it needs a browser. Only a
 * localStorage shim is required, installed before the module is imported.
 */

// ── localStorage shim, installed before importing store.js ───────────────

function makeLocalStorage() {
  const ls = {};
  const define = (name, value) =>
    Object.defineProperty(ls, name, { value, enumerable: false });
  define('getItem', (k) => (Object.prototype.hasOwnProperty.call(ls, k) ? ls[k] : null));
  define('setItem', (k, v) => { ls[k] = String(v); });
  define('removeItem', (k) => { delete ls[k]; });
  define('clear', () => { for (const k of Object.keys(ls)) delete ls[k]; });
  define('key', (i) => Object.keys(ls)[i] ?? null);
  Object.defineProperty(ls, 'length', { get: () => Object.keys(ls).length, enumerable: false });
  return ls;
}

globalThis.localStorage = makeLocalStorage();

const { store, todayStr, addDays, weekDates, currentCycleKey, formatDate } =
  await import('../docs/js/store.js');
const { applyCheckin, emptyState } = await import('../docs/js/merge.js');

let passed = 0;
const failures = [];

function check(name, condition, detail) {
  if (condition) passed++;
  else failures.push(detail ? `${name}\n    ${detail}` : name);
}

function eq(name, actual, expected) {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  check(name, a === b, `expected ${b}, got ${a}`);
}

/** Reset to a clean slate; the store is a module singleton. */
function reset() {
  localStorage.clear();
  store.state = emptyState();
  store.collapsed = new Set();
  store.dirty = false;
  store.lang = 'zh';
  store.selectedDate = todayStr();
  store.weekRef = store.selectedDate;
}

const TODAY = todayStr();

// ── Groups and habits ────────────────────────────────────────────────────

reset();
const g1 = store.addGroup('雅思', 'IELTS', '#881798');
const g2 = store.addGroup('学习', 'Study', '#0078d4');
check('addGroup returns an id', typeof g1 === 'string' && g1.startsWith('g_'));
eq('groups sort by order', store.groups().map((g) => g.id), [g1, g2]);
eq('groupName follows language', [store.groupName(g1), (store.setLang('en'), store.groupName(g1))],
  ['雅思', 'IELTS']);
store.setLang('zh');

check('addGroup rejects a blank name', store.addGroup('   ', '', '') === null);

const h1 = store.addHabit('单词复习', g1);
const h2 = store.addHabit('百词斩新词打卡', g1);
const h3 = store.addHabit('阅读 30 分钟', g2);
check('addHabit returns an id', typeof h1 === 'string');
check('addHabit rejects a blank name', store.addHabit('  ', g1) === null);
eq('habits are scoped to their group',
  store.habitsInGroup(g1).map((h) => h.id), [h1, h2]);
eq('new habits append to the end of their group', store.habitsInGroup(g2).map((h) => h.id), [h3]);

// ── Ordering: within a group, never across ───────────────────────────────

store.moveHabit(h2, -1);
eq('moveHabit swaps within the group', store.habitsInGroup(g1).map((h) => h.id), [h2, h1]);
check('moveHabit at the top edge returns false', store.moveHabit(h2, -1) === false);
check('moveHabit at the bottom edge returns false', store.moveHabit(h1, 1) === false);
eq('a group move does not disturb the other group',
  store.habitsInGroup(g2).map((h) => h.id), [h3]);
eq('orders stay spaced after a move',
  store.habitsInGroup(g1).map((h) => h.order), [0, 10]);

store.moveHabitToGroup(h3, g1);
eq('moveHabitToGroup appends to the target group',
  store.habitsInGroup(g1).map((h) => h.id), [h2, h1, h3]);
eq('the source group is now empty', store.habitsInGroup(g2), []);

// ── Check-ins ────────────────────────────────────────────────────────────

check('a fresh habit is unchecked', store.isChecked(h1, TODAY) === false);
check('toggleCheckin returns the new state', store.toggleCheckin(h1, TODAY) === true);
check('toggleCheckin round-trips', store.toggleCheckin(h1, TODAY) === false);
store.toggleCheckin(h1, TODAY);

check('total counts only positive cells', store.total(h1) === 1);
check('a check-in on one date leaves others alone', store.isChecked(h1, addDays(TODAY, -1)) === false);
check('checking a habit does not affect its siblings', store.isChecked(h2, TODAY) === false);
check('a check-in marks the store dirty', store.dirty === true);

// ── Streaks ──────────────────────────────────────────────────────────────
// Anchored at yesterday when today is empty, so the UI does not report a
// broken streak every morning before the first check-in of the day.

reset();
const gh = store.addGroup('G', 'G', '#0078d4');
const habit = store.addHabit('H', gh);
const put = (offset) => applyCheckin(store.state, habit, addDays(TODAY, offset), true, 1000);

eq('streak with nothing checked is 0', store.streak(habit), 0);
put(0);
eq('streak with only today is 1', store.streak(habit), 1);
put(-1);
eq('streak counts consecutive days back from today', store.streak(habit), 2);
put(-2);
eq('streak reaches 3', store.streak(habit), 3);

reset();
const gh2 = store.addGroup('G', 'G', '#0078d4');
const hb = store.addHabit('H', gh2);
applyCheckin(store.state, hb, addDays(TODAY, -1), true, 1000);
applyCheckin(store.state, hb, addDays(TODAY, -2), true, 1001);
eq('streak counts from yesterday when today is not yet checked', store.streak(hb), 2);

applyCheckin(store.state, hb, addDays(TODAY, -4), true, 1002);
eq('a gap ends the streak', store.streak(hb), 2);

reset();
const gh3 = store.addGroup('G', 'G', '#0078d4');
const hc = store.addHabit('H', gh3);
applyCheckin(store.state, hc, addDays(TODAY, -3), true, 1000);
eq('an old check-in with nothing recent is not a streak', store.streak(hc), 0);

// ── Weekly completion rate ───────────────────────────────────────────────
// Denominator is elapsed days, not all 7: the desktop version scored a
// perfect Monday at 14%.

reset();
const gw = store.addGroup('G', 'G', '#0078d4');
const hw = store.addHabit('H', gw);
const week = weekDates(TODAY);
const elapsed = week.filter((d) => d <= TODAY);

eq('week rate with nothing checked is 0', store.weekCompletionRate(), 0);
for (const day of elapsed) applyCheckin(store.state, hw, day, true, 1000);
eq('a perfect week-to-date is 100%, not a fraction', store.weekCompletionRate(), 100);

// Future days must not count against the user.
const future = week.filter((d) => d > TODAY);
check('the week contains future days on most days of the week',
  future.length > 0 || elapsed.length === 7);
check('rate stays 100 while future days are unchecked',
  store.weekCompletionRate() === 100);

applyCheckin(store.state, hw, elapsed[0], false, 2000);
const expected = Math.round(((elapsed.length - 1) / elapsed.length) * 100);
eq('un-checking one elapsed day lowers the rate proportionally',
  store.weekCompletionRate(), expected);

// ── allDoneOn ────────────────────────────────────────────────────────────

reset();
const ga = store.addGroup('G', 'G', '#0078d4');
const a1 = store.addHabit('A', ga);
const a2 = store.addHabit('B', ga);
check('allDoneOn is false with no check-ins', store.allDoneOn(TODAY) === false);
store.toggleCheckin(a1, TODAY);
check('allDoneOn is false when only some habits are checked', store.allDoneOn(TODAY) === false);
store.toggleCheckin(a2, TODAY);
check('allDoneOn is true when every habit is checked', store.allDoneOn(TODAY) === true);
store.toggleCheckin(a2, TODAY);
check('allDoneOn reverts when one is un-checked', store.allDoneOn(TODAY) === false);

reset();
check('allDoneOn is false with no habits at all', store.allDoneOn(TODAY) === false);

// ── Deletion ─────────────────────────────────────────────────────────────

reset();
const gd = store.addGroup('临时', 'Temp', '#0078d4');
const d1 = store.addHabit('X', gd);
const d2 = store.addHabit('Y', gd);
store.toggleCheckin(d1, TODAY);

const removed = store.deleteGroup(gd);
check('deleteGroup reports what it removed',
  removed && removed.habits.length === 2 && removed.group.id === gd);
eq('the group is gone from the live set', store.groups().map((g) => g.id), []);
eq('its habits are gone too', store.habits().map((h) => h.id), []);
check('the check-in history is preserved, not erased',
  store.state.checkins[d1] && Object.keys(store.state.checkins[d1]).length === 1);

reset();
const gk = store.addGroup('G', 'G', '#0078d4');
const k1 = store.addHabit('X', gk);
const snapshot = store.deleteHabit(k1);
check('deleteHabit returns a snapshot for undo', snapshot && snapshot.id === k1);
eq('the deleted habit is not live', store.habits().map((h) => h.id), []);
check('deletion is a tombstone, not a removal', store.state.habits[k1].deleted === true);

store.state.habits[k1] = { ...snapshot, deleted: false };
eq('restoring the snapshot brings it back', store.habits().map((h) => h.id), [k1]);

// ── Local-only preferences must not reach the synced state ───────────────

reset();
const gp = store.addGroup('G', 'G', '#0078d4');
store.toggleCollapsed(gp);
store.setLang('en');
store.setSelectedDate(addDays(TODAY, -1));

const serialised = JSON.stringify(store.state);
check('collapsed is not in the synced state', !serialised.includes('collapsed'));
check('lang is not in the synced state', !serialised.includes('"lang"'));
check('selectedDate is not in the synced state', !serialised.includes('selectedDate'));
check('collapsed survives in localStorage', store.collapsed.has(gp));
eq('language persists', store.lang, 'en');

// ── Week paging keeps the selection visible ──────────────────────────────

reset();
store.setWeekRef(addDays(TODAY, -14));
check('paging weeks moves the selection into the visible week',
  weekDates(store.weekRef).includes(store.selectedDate),
  `selected=${store.selectedDate} week=${weekDates(store.weekRef).join(',')}`);

// ── Cycle keys ───────────────────────────────────────────────────────────

eq('daily cycle key is the date', currentCycleKey('daily', '2026-09-16'), '2026-09-16');
eq('monthly cycle key is the month', currentCycleKey('monthly', '2026-09-16'), '2026-09');
eq('weekly cycle key is the ISO week', currentCycleKey('weekly', '2026-09-16'), '2026-W38');
eq('ISO week handles a year boundary', currentCycleKey('weekly', '2026-01-01'), '2026-W01');

// ── Report ───────────────────────────────────────────────────────────────

const total = passed + failures.length;
if (failures.length) {
  console.error(`\n${failures.length} of ${total} checks FAILED:\n`);
  for (const f of failures) console.error(`  x ${f}`);
  process.exit(1);
}
console.log(`OK all ${total} store checks passed`);
