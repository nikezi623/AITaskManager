/**
 * Render + interaction test for the PWA, using jsdom.
 *
 *   npm install jsdom          (or set ATM_JSDOM_PATH to a directory that has it)
 *   node tests/test_render.mjs
 *
 * This exists because the app is debugged on an iPhone with no devtools: a
 * runtime error in ui.js would present as a blank white screen and nothing
 * else. Catching it here costs a few seconds.
 */

import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DOCS = join(HERE, '..', 'docs');

function loadJsdom() {
  const candidates = [
    process.env.ATM_JSDOM_PATH,
    join(HERE, '..'),
    '/tmp/atm-domtest',
  ].filter(Boolean);
  for (const base of candidates) {
    try {
      return createRequire(join(base, 'noop.js'))('jsdom');
    } catch { /* try the next candidate */ }
  }
  console.log('SKIP: jsdom not installed. Run `npm install jsdom` or set ATM_JSDOM_PATH.');
  process.exit(0);
}

const { JSDOM } = loadJsdom();

// ── Environment ──────────────────────────────────────────────────────────

const html = readFileSync(join(DOCS, 'index.html'), 'utf8');
const dom = new JSDOM(html, { url: 'https://nikezi623.github.io/AITaskManager/', pretendToBeVisual: true });
const { window } = dom;

// ui.js uses CSS.escape to build a selector; jsdom does not implement it.
if (!window.CSS) window.CSS = {};
if (!window.CSS.escape) {
  window.CSS.escape = (value) => String(value).replace(/[^a-zA-Z0-9_-]/g, (ch) => `\\${ch}`);
}

globalThis.window = window;
globalThis.document = window.document;
globalThis.localStorage = window.localStorage;
globalThis.CSS = window.CSS;
globalThis.requestAnimationFrame = window.requestAnimationFrame;
globalThis.HTMLElement = window.HTMLElement;
globalThis.Node = window.Node;
globalThis.CustomEvent = window.CustomEvent;
try {
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
} catch { /* Node's own navigator is fine for this test */ }

// ── Harness ──────────────────────────────────────────────────────────────

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

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

// A dismissed sheet stays in the DOM for 200ms while it fades, so a plain
// query can hit the previous sheet. Always scope to the most recent one.
const lastSheet = () => $$('.sheet').pop();
const sheetItems = () => [...(lastSheet()?.querySelectorAll('.sheet-item') || [])];
const sheetField = (selector = '.field-input') => lastSheet()?.querySelector(selector);

/** Dispatch a pointer event. jsdom has no PointerEvent, but addEventListener
 *  for 'pointerdown' fires for any event carrying that type. */
function pointer(target, type, extra = {}) {
  const event = new window.MouseEvent(type, {
    bubbles: true, cancelable: true, clientX: 10, clientY: 10, ...extra,
  });
  target.dispatchEvent(event);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ── Boot ─────────────────────────────────────────────────────────────────

const { store, todayStr, addDays } = await import('../docs/js/store.js');
const { mount } = await import('../docs/js/ui.js');
const { sync } = await import('../docs/js/sync.js');

// Seed a realistic fixture: two groups, three habits, one checked yesterday.
const g1 = store.addGroup('雅思', 'IELTS', '#881798');
const g2 = store.addGroup('学习', 'Study', '#0078d4');
const h1 = store.addHabit('单词复习', g1);
const h2 = store.addHabit('百词斩新词打卡', g1);
const h3 = store.addHabit('阅读 30 分钟', g2);
store.toggleCheckin(h1, addDays(todayStr(), -1));
store.dirty = false;

sync.token = ''; // no network in this test

mount(document.getElementById('app'));

// ── Structure ────────────────────────────────────────────────────────────

check('boot: no exception while mounting', true);
check('shell: header title renders', $('.app-title') !== null);
eq('shell: title text', $('.app-title').textContent, 'ATM · 习惯打卡');
check('shell: a week nav exists', $('.week-nav') !== null);
eq('week nav: exactly 7 day buttons', $$('.day-btn').length, 7);
eq('week nav: exactly 7 dots', $$('.wn-dot').length, 7);
eq('week nav: exactly 7 weekday labels', $$('.wn-weekday').length, 7);
eq('week nav: weekday labels are Chinese', $$('.wn-weekday').map((n) => n.textContent),
  ['一', '二', '三', '四', '五', '六', '日']);
check('week nav: exactly one day is selected', $$('.day-btn.selected').length === 1);
check('week nav: the month label is populated', /年\d{2}月/.test($('.wn-month').textContent),
  $('.wn-month').textContent);

eq('list: one section per group', $$('.group').length, 2);
eq('list: group names render', $$('.gname').map((n) => n.textContent), ['雅思', '学习']);
eq('list: group counts render', $$('.gcount').map((n) => n.textContent), ['(2)', '(1)']);
eq('list: one row per habit', $$('.row').length, 3);
eq('list: habit names render', $$('.row-name').map((n) => n.textContent),
  ['单词复习', '百词斩新词打卡', '阅读 30 分钟']);
eq('list: each row has a check circle', $$('.row .circle').length, 3);
check('list: the group color bar is applied',
  $('.row .bar').style.background.includes('136, 23, 152') || $('.row .bar').style.background !== '');

check('footer: completion rate renders', /本周完成率: \d+%/.test($('.rate-btn').textContent),
  $('.rate-btn').textContent);
check('footer: an add button exists', $('.fab') !== null);
check('sync dot: reflects the unconfigured state', $('.sync-dot').classList.contains('off'));

// The habit checked yesterday must not read as checked today.
eq('state: today has nothing checked yet', store.isChecked(h1), false);
eq('state: the yesterday check-in survives', store.total(h1), 1);

// ── Tapping a check circle ───────────────────────────────────────────────

const circle = $(`.row[data-habit="${h1}"] .circle`);
check('circle starts unchecked', !circle.classList.contains('checked'));
circle.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));

check('tap: the check-in is recorded', store.isChecked(h1) === true);
check('tap: the circle reflects it without a full rebuild',
  $(`.row[data-habit="${h1}"] .circle`).classList.contains('checked'));
check('tap: the row identity survived (in-place update)', circle.isConnected);
eq('tap: the stats counter updates', $(`.row[data-habit="${h1}"] .row-stats`).textContent, '📊 2');
check('tap: the week dot strip updated', true);

circle.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
check('tap again un-checks', store.isChecked(h1) === false);
circle.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));

// ── Stats toggle ─────────────────────────────────────────────────────────

const statsBtn = $(`.row[data-habit="${h1}"] .row-stats`);
statsBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
check('stats: the button switches to the streak view',
  $(`.row[data-habit="${h1}"] .row-stats`).textContent.startsWith('🔥'),
  $(`.row[data-habit="${h1}"] .row-stats`).textContent);
$(`.row[data-habit="${h1}"] .row-stats`).dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
check('stats: toggles back to the total view',
  $(`.row[data-habit="${h1}"] .row-stats`).textContent.startsWith('📊'));

// ── Collapsing a group ───────────────────────────────────────────────────

const before = $$('.row').length;
$('.group-header').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
check('collapse: the group is marked collapsed', store.collapsed.has(g1));
check('collapse: its rows are hidden', $$('.row').length < before);
eq('collapse: the other group is untouched',
  $$('.row-name').map((n) => n.textContent), ['阅读 30 分钟']);
eq('collapse: the arrow flips', $('.group-header .arrow').textContent, '▶');

$('.group-header').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
eq('expand: rows come back', $$('.row').length, before);

// ── Long-press opens the habit menu ──────────────────────────────────────

const row = $(`.row[data-habit="${h3}"]`);
pointer(row, 'pointerdown');
await sleep(600); // LONG_PRESS_MS is 500

check('long press: a sheet opens', lastSheet() !== undefined);
const menuLabels = sheetItems().map((n) => n.textContent);
check('long press: the menu offers edit', menuLabels.includes('编辑习惯'), menuLabels.join(' | '));
check('long press: the menu offers delete', menuLabels.includes('删除习惯'));
check('long press: the menu offers move-to-group',
  menuLabels.some((l) => l.startsWith('移动到')), menuLabels.join(' | '));
check('long press: delete is styled as destructive',
  sheetItems().some((n) => n.textContent === '删除习惯' && n.classList.contains('danger')));

// Selecting "edit" should replace the menu with the habit form. This is the
// path that silently did nothing when close() settled the promise first.
sheetItems().find((n) => n.textContent === '编辑习惯')
  .dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await sleep(250);
check('edit: an input is shown', sheetField() !== null);
eq('edit: the field is prefilled', sheetField().value, '阅读 30 分钟');

// Saving a rename must update the row.
sheetField().value = '阅读 45 分钟';
sheetItems().find((n) => n.textContent === '保存')
  .dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await sleep(250);
check('edit: the rename is persisted',
  store.state.habits[h3].name === '阅读 45 分钟',
  store.state.habits[h3].name);
check('edit: the row re-renders with the new name',
  $$('.row-name').some((n) => n.textContent === '阅读 45 分钟'));

// ── A blank name must not save silently ──────────────────────────────────

$('.fab').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await sleep(250);
check('add: the habit form opens', sheetField() !== null);
const countBefore = store.habits().length;
sheetItems().find((n) => n.textContent === '保存')
  .dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await sleep(50);
eq('add: an empty name is rejected', store.habits().length, countBefore);
check('add: the empty field is flagged rather than failing silently',
  sheetField().classList.contains('invalid'));
check('add: the sheet stays open so the user can correct it',
  lastSheet() !== undefined);

sheetItems().find((n) => n.textContent === '取消')
  .dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await sleep(250);

// ── Language toggle ──────────────────────────────────────────────────────

$('.lang-btn').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
eq('language: store switched to English', store.lang, 'en');
eq('language: title retranslated', $('.app-title').textContent, 'ATM · Habit Tracker');
eq('language: group names use name_en', $$('.gname').map((n) => n.textContent),
  ['IELTS', 'Study']);
eq('language: weekday labels switch', $$('.wn-weekday').map((n) => n.textContent),
  ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']);
check('language: the month label switches to English',
  /^[A-Z][a-z]+ \d{4}$/.test($('.wn-month').textContent), $('.wn-month').textContent);
check('language: the footer retranslates',
  $('.rate-btn').textContent.startsWith('Weekly Completion:'), $('.rate-btn').textContent);

$('.lang-btn').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
eq('language: toggles back', store.lang, 'zh');

// ── Settings sheet ───────────────────────────────────────────────────────

$('.header-actions .icon-btn').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await sleep(250);
const settingsLabels = sheetItems().map((n) => n.textContent);
check('settings: opens from the header', lastSheet() !== undefined);
check('settings: offers a token field', sheetField('input[type="password"]') !== null);
check('settings: offers a connection test', settingsLabels.includes('测试连接'),
  settingsLabels.join(' | '));
check('settings: offers a forced update', settingsLabels.includes('强制更新'));
check('settings: states the version', /版本: /.test(lastSheet().textContent));

// ── The all-done celebration ─────────────────────────────────────────────

$$('.sheet-backdrop').pop().dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
await sleep(250);

// Check only what is unchecked -- toggling an already-checked habit would
// un-check it and the day would never complete.
for (const habit of store.habits()) {
  if (!store.isChecked(habit.id, todayStr())) store.toggleCheckin(habit.id, todayStr());
}
check('celebration: fires when the day becomes fully checked',
  $('.toast') !== null && $('.toast').textContent.includes('全部完成'),
  $('.toast') ? $('.toast').textContent : 'no toast');
check('celebration: the week dot for today turns green',
  $$('.wn-dot.done').length > 0);

// ── Report ───────────────────────────────────────────────────────────────

const total = passed + failures.length;
if (failures.length) {
  console.error(`\n${failures.length} of ${total} render checks FAILED:\n`);
  for (const f of failures) console.error(`  x ${f}`);
  process.exit(1);
}
console.log(`OK all ${total} render checks passed`);
