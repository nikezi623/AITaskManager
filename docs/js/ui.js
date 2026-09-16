/**
 * Rendering and interaction.
 *
 * Check-ins update the affected row, the week-dot strip and the footer in
 * place; only structural changes (add/delete/reorder/group) rebuild the list.
 * A full rebuild on every tap would kill the circle's transition and can jog
 * the scroll position -- and check-in is by far the most common action.
 */

import { addDays, store, todayStr, weekDates } from './store.js';
import { SyncStatus, sync } from './sync.js';
import { ErrorKind } from './github.js';
import { formatMonth, makeT, weekdayLabels } from './i18n.js';
import {
  onLongPress, primeAudio, showConfirm, showMenu, openSheet, tick, toast,
} from './gestures.js';

const GROUP_COLORS = ['#0078d4', '#ff8c00', '#881798', '#107c10',
  '#d13438', '#00b7c3', '#498205', '#e81123'];

const refs = {};
let t = makeT(store.lang);
let showStreak = new Set();   // habit ids currently displaying 🔥 instead of 📊
let lastAllDone = null;       // to fire the celebration only on a false->true edge
let lastSignature = null;     // last rendered structure, to skip needless rebuilds

const $ = (id) => document.getElementById(id);

// ── Shell ────────────────────────────────────────────────────────────────

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function buildShell(container) {
  container.innerHTML = '';

  const header = el('header', 'app-header');
  refs.title = el('h1', 'app-title', t('title'));
  const actions = el('div', 'header-actions');
  refs.syncDot = el('span', 'sync-dot');
  refs.settingsBtn = el('button', 'icon-btn', '⚙');
  refs.settingsBtn.setAttribute('aria-label', t('settings'));
  refs.langBtn = el('button', 'lang-btn', t('lang'));
  actions.append(refs.syncDot, refs.settingsBtn, refs.langBtn);
  header.append(refs.title, actions);

  refs.weekNav = el('nav', 'week-nav');
  buildWeekNav();

  refs.list = el('div', 'habit-list');
  refs.scroll = el('main', 'habit-scroll');
  refs.scroll.appendChild(refs.list);

  const footer = el('footer', 'app-footer');
  refs.rate = el('button', 'rate-btn');
  refs.statsBtn = el('button', 'icon-btn', '📊');
  refs.statsBtn.setAttribute('aria-label', t('stats_title'));
  refs.addBtn = el('button', 'fab', '+');
  refs.addBtn.setAttribute('aria-label', t('add_habit'));
  footer.append(refs.rate, refs.statsBtn, refs.addBtn);

  container.append(header, refs.weekNav, refs.scroll, footer);

  // Long-press on empty space opens the create menu, like the desktop app's
  // right-click on the window background.
  onLongPress(refs.scroll, (event) => {
    if (event.target.closest('.row, .group-header, button, .add-inline')) return;
    openCreateMenu();
  });
  // A plain tap on empty space dismisses any open sheet.
  refs.scroll.addEventListener('click', (event) => {
    if (event.target.closest('.row, .group-header, button')) return;
  });

  refs.settingsBtn.addEventListener('click', openSettings);
  refs.langBtn.addEventListener('click', () => {
    store.setLang(store.lang === 'zh' ? 'en' : 'zh');
  });
  refs.statsBtn.addEventListener('click', openStats);
  refs.addBtn.addEventListener('click', () => openHabitDialog(null));
  refs.rate.addEventListener('click', () => sync.run('manual'));
}

// ── Week navigation ──────────────────────────────────────────────────────

function buildWeekNav() {
  refs.weekNav.innerHTML = '';
  const top = el('div', 'wn-row wn-top');
  const prev = el('button', 'wn-arrow', '◀');
  const next = el('button', 'wn-arrow', '▶');
  refs.monthLabel = el('span', 'wn-month');
  prev.setAttribute('aria-label', 'previous week');
  next.setAttribute('aria-label', 'next week');
  // Paging moves the selection into the visible week -- otherwise tapping a
  // circle edits a day you cannot see.
  prev.addEventListener('click', () => store.setWeekRef(addDays(store.weekRef, -7)));
  next.addEventListener('click', () => store.setWeekRef(addDays(store.weekRef, 7)));
  top.append(prev, refs.monthLabel, el('span', 'wn-spacer'), next);

  refs.daysRow = el('div', 'wn-row wn-days');
  refs.metaRow = el('div', 'wn-row wn-meta');
  refs.weekNav.append(top, refs.daysRow, refs.metaRow);
}

function renderWeekNav() {
  const days = weekDates(store.weekRef);
  const today = todayStr();
  const labels = weekdayLabels(store.lang);
  const date = new Date(`${days[0]}T00:00:00Z`);
  refs.monthLabel.textContent = formatMonth(date.getUTCFullYear(), date.getUTCMonth(), store.lang);

  refs.daysRow.innerHTML = '';
  refs.metaRow.innerHTML = '';

  days.forEach((day, index) => {
    const dayNumber = Number(day.slice(8, 10));
    const button = el('button', 'day-btn', String(dayNumber));
    button.dataset.date = day;
    if (day === store.selectedDate) button.classList.add('selected');
    else if (day === today) button.classList.add('today');
    button.addEventListener('click', () => {
      primeAudio();
      tick(true);
      store.setSelectedDate(day);
    });
    refs.daysRow.appendChild(button);

    const cell = el('div', 'wn-cell');
    cell.appendChild(el('span', 'wn-weekday', labels[index]));
    const dot = el('span', 'wn-dot');
    dot.dataset.date = day;
    cell.appendChild(dot);
    refs.metaRow.appendChild(cell);
  });
  updateWeekDots();
}

/** Update the existing day buttons in place, without rebuilding them. */
function paintWeekNav() {
  const days = weekDates(store.weekRef);
  const today = todayStr();
  refs.daysRow.querySelectorAll('.day-btn').forEach((button, index) => {
    const day = days[index];
    button.classList.toggle('selected', day === store.selectedDate);
    button.classList.toggle('today', day === today && day !== store.selectedDate);
  });
  updateWeekDots();
}

function updateWeekDots() {
  for (const dot of refs.metaRow.querySelectorAll('.wn-dot')) {
    dot.classList.toggle('done', store.allDoneOn(dot.dataset.date));
  }
}

// ── Habit list ───────────────────────────────────────────────────────────

function renderList() {
  refs.list.innerHTML = '';
  const groups = store.groups();

  if (!groups.length) {
    refs.list.appendChild(el('p', 'empty-state', t('no_habits')));
    return;
  }

  for (const group of groups) {
    const habits = store.habitsInGroup(group.id);
    const collapsed = store.collapsed.has(group.id);
    const section = el('section', 'group');

    const header = el('button', 'group-header');
    header.append(
      el('span', 'arrow', collapsed ? '▶' : '▼'),
      el('span', 'gname', store.groupName(group.id)),
      el('span', 'gcount', `(${habits.length})`),
    );
    header.addEventListener('click', () => {
      primeAudio();
      store.toggleCollapsed(group.id);
    });
    onLongPress(header, () => openGroupMenu(group));
    section.appendChild(header);

    if (!collapsed) {
      const body = el('div', 'group-body');
      for (const habit of habits) body.appendChild(buildRow(habit, group));
      const addInline = el('button', 'add-inline', `+ ${t('add_habit')}`);
      addInline.addEventListener('click', () => openHabitDialog(null, group.id));
      body.appendChild(addInline);
      section.appendChild(body);
    }
    refs.list.appendChild(section);
  }
}

function buildRow(habit, group) {
  const row = el('div', 'row');
  row.dataset.habit = habit.id;
  const bar = el('span', 'bar');
  bar.style.background = group.color || '#0078d4';
  const name = el('span', 'row-name', habit.name);
  const stats = el('button', 'row-stats');
  const circle = el('button', 'circle');
  circle.dataset.habit = habit.id;

  row.append(bar, name, stats, circle);
  paintRow(row);

  circle.addEventListener('click', (event) => {
    event.stopPropagation();
    primeAudio();
    const checked = store.toggleCheckin(habit.id);
    tick(checked);
  });

  stats.addEventListener('click', (event) => {
    event.stopPropagation();
    primeAudio();
    if (showStreak.has(habit.id)) showStreak.delete(habit.id);
    else showStreak.add(habit.id);
    paintRow(row);
  });

  onLongPress(row, () => openHabitMenu(habit));
  return row;
}

function paintRow(row) {
  const habitId = row.dataset.habit;
  const habit = store.state.habits[habitId];
  if (!habit) return;
  const checked = store.isChecked(habitId);
  row.querySelector('.circle').classList.toggle('checked', checked);
  row.querySelector('.circle').setAttribute('aria-pressed', String(checked));
  row.querySelector('.row-name').textContent = habit.name;
  const stats = row.querySelector('.row-stats');
  stats.textContent = showStreak.has(habitId)
    ? `🔥 ${store.streak(habitId)}`
    : `📊 ${store.total(habitId)}`;
}

function updateRow(habitId) {
  const row = refs.list.querySelector(`.row[data-habit="${CSS.escape(habitId)}"]`);
  if (row) paintRow(row);
}

// ── Footer ───────────────────────────────────────────────────────────────

function renderFooter() {
  refs.rate.textContent = `${t('week_completion')}: ${store.weekCompletionRate()}%`;
  paintSyncDot();
}

function paintSyncDot() {
  const dot = refs.syncDot;
  dot.className = 'sync-dot';
  if (!sync.hasToken) {
    dot.classList.add('off');
    dot.title = t('never_synced');
    return;
  }
  if (sync.status === SyncStatus.SYNCING) {
    dot.classList.add('busy');
    dot.title = t('syncing');
    return;
  }
  if (store.dirty) {
    dot.classList.add('pending');
    dot.title = t('sync_pending');
    return;
  }
  if (sync.status === SyncStatus.ERROR || sync.status === SyncStatus.OFFLINE) {
    dot.classList.add('error');
    dot.title = t('sync_failed');
    return;
  }
  dot.classList.add('ok');
  dot.title = sync.lastSyncAt
    ? t('synced_at', { time: new Date(sync.lastSyncAt).toTimeString().slice(0, 5) })
    : t('never_synced');
}

// ── Sheets and dialogs ───────────────────────────────────────────────────

async function openHabitMenu(habit) {
  const groups = store.groups().filter((g) => g.id !== habit.groupId);
  const items = [
    { key: 'edit', label: t('edit_habit') },
    { key: 'up', label: `↑ ${t('move_up')}` },
    { key: 'down', label: `↓ ${t('move_down')}` },
    { separator: true },
  ];
  for (const group of groups) {
    items.push({ key: `move:${group.id}`, label: `${t('move_to')} · ${store.groupName(group.id)}` });
  }
  if (groups.length) items.push({ separator: true });
  items.push({ key: 'delete', label: t('delete_habit'), danger: true });

  const choice = await showMenu(items, { title: habit.name, cancelLabel: t('cancel') });
  if (!choice) return;

  if (choice.key === 'edit') openHabitDialog(habit);
  else if (choice.key === 'up') {
    if (!store.moveHabit(habit.id, -1)) {
      toast(store.lang === 'zh' ? '已经在最前面了' : 'Already first');
    }
  } else if (choice.key === 'down') {
    if (!store.moveHabit(habit.id, 1)) {
      toast(store.lang === 'zh' ? '已经在最后面了' : 'Already last');
    }
  } else if (choice.key.startsWith('move:')) {
    store.moveHabitToGroup(habit.id, choice.key.slice(5));
  } else if (choice.key === 'delete') {
    const ok = await showConfirm({
      title: t('delete_habit'),
      message: t('confirm_delete_habit', { name: habit.name }),
      confirmLabel: t('delete'),
      cancelLabel: t('cancel'),
      danger: true,
    });
    if (!ok) return;
    const snapshot = store.deleteHabit(habit.id);
    if (snapshot) {
      toast(t('deleted_habit', { name: snapshot.name }), {
        actionLabel: t('undo'),
        onAction: () => restoreHabit(snapshot),
      });
    }
  }
}

/** Undo for deletion -- the desktop app has none, and a misfired long-press
 *  on a phone should not destroy a habit with months of history. */
function restoreHabit(snapshot) {
  store.state.habits[snapshot.id] = { ...snapshot, deleted: false };
  const habit = store.state.habits[snapshot.id];
  habit.updatedAt = Math.floor(Date.now() / 1000);
  habit.writer = store.deviceId;
  store.dirty = true;
  store.persist();
  store.emit();
}

async function openGroupMenu(group) {
  const choice = await showMenu([
    { key: 'edit', label: t('edit_group') },
    { key: 'add', label: t('add_habit') },
    { separator: true },
    { key: 'delete', label: t('delete_group'), danger: true },
  ], { title: store.groupName(group.id), cancelLabel: t('cancel') });
  if (!choice) return;

  if (choice.key === 'edit') openGroupDialog(group);
  else if (choice.key === 'add') openHabitDialog(null, group.id);
  else if (choice.key === 'delete') {
    const count = store.habitsInGroup(group.id).length;
    let message = t('confirm_delete_group', { name: store.groupName(group.id) });
    if (count) message += `\n\n${t('group_has_habits', { n: count })}`;
    const ok = await showConfirm({
      title: t('delete_group'), message,
      confirmLabel: t('delete'), cancelLabel: t('cancel'), danger: true,
    });
    if (!ok) return;
    const removed = store.deleteGroup(group.id);
    if (removed) {
      const name = removed.group.name_zh;
      toast(t('deleted_group', { name }), {
        actionLabel: t('undo'),
        onAction: () => {
          restoreRecord('groups', removed.group);
          for (const habit of removed.habits) restoreRecord('habits', habit);
          store.dirty = true;
          store.persist();
          store.emit();
        },
      });
    }
  }
}

function restoreRecord(table, snapshot) {
  store.state[table][snapshot.id] = { ...snapshot, deleted: false };
  const record = store.state[table][snapshot.id];
  record.updatedAt = Math.floor(Date.now() / 1000);
  record.writer = store.deviceId;
}

function openCreateMenu() {
  showMenu([
    { key: 'habit', label: t('add_habit') },
    { key: 'group', label: t('add_group') },
  ], { cancelLabel: t('cancel') }).then((choice) => {
    if (!choice) return;
    if (choice.key === 'habit') openHabitDialog(null);
    else openGroupDialog(null);
  });
}

function openHabitDialog(habit, presetGroupId) {
  const groups = store.groups();
  let groupId = habit ? habit.groupId : (presetGroupId || (groups[0] && groups[0].id));

  openSheet({
    title: habit ? t('edit_habit') : t('add_habit'),
    build(body, close) {
      const nameLabel = el('label', 'field-label', t('habit_name'));
      const nameInput = el('input', 'field-input');
      nameInput.type = 'text';
      nameInput.value = habit ? habit.name : '';
      nameInput.placeholder = t('habit_name');
      nameInput.autocomplete = 'off';

      const groupLabel = el('label', 'field-label', t('select_group'));
      const groupSelect = el('select', 'field-input');
      for (const group of groups) {
        const option = el('option', null, store.groupName(group.id));
        option.value = group.id;
        if (group.id === groupId) option.selected = true;
        groupSelect.appendChild(option);
      }
      groupSelect.addEventListener('change', () => { groupId = groupSelect.value; });

      const save = el('button', 'sheet-item primary', t('save'));
      save.addEventListener('click', () => {
        const name = nameInput.value.trim();
        if (!name) {
          nameInput.classList.add('invalid');
          nameInput.focus();
          return; // the desktop version failed silently here
        }
        if (habit) store.editHabit(habit.id, { name, groupId });
        else store.addHabit(name, groupId);
        close();
      });
      const cancel = el('button', 'sheet-item cancel', t('cancel'));
      cancel.addEventListener('click', close);

      body.append(nameLabel, nameInput, groupLabel, groupSelect, save, cancel);
      setTimeout(() => nameInput.focus(), 250);
    },
  });
}

function openGroupDialog(group) {
  let color = group ? group.color : GROUP_COLORS[store.groups().length % GROUP_COLORS.length];

  openSheet({
    title: group ? t('edit_group') : t('add_group'),
    build(body, close) {
      const zhLabel = el('label', 'field-label', t('group_name_zh'));
      const zhInput = el('input', 'field-input');
      zhInput.type = 'text';
      zhInput.value = group ? group.name_zh : '';

      const enLabel = el('label', 'field-label', t('group_name_en'));
      const enInput = el('input', 'field-input');
      enInput.type = 'text';
      enInput.value = group ? group.name_en : '';

      const colorLabel = el('label', 'field-label', t('group_color'));
      const swatches = el('div', 'swatches');
      const buttons = [];
      const paintSwatches = () => {
        buttons.forEach((button, index) => {
          button.classList.toggle('active', GROUP_COLORS[index] === color);
        });
      };
      GROUP_COLORS.forEach((candidate) => {
        const swatch = el('button', 'swatch');
        swatch.style.background = candidate;
        swatch.addEventListener('click', () => { color = candidate; paintSwatches(); });
        buttons.push(swatch);
        swatches.appendChild(swatch);
      });
      paintSwatches();

      const save = el('button', 'sheet-item primary', t('save'));
      save.addEventListener('click', () => {
        const zh = zhInput.value.trim();
        if (!zh) {
          zhInput.classList.add('invalid');
          zhInput.focus();
          return;
        }
        const en = enInput.value.trim();
        if (group) store.editGroup(group.id, { nameZh: zh, nameEn: en, color });
        else store.addGroup(zh, en, color);
        close();
      });
      const cancel = el('button', 'sheet-item cancel', t('cancel'));
      cancel.addEventListener('click', close);

      body.append(zhLabel, zhInput, enLabel, enInput, colorLabel, swatches, save, cancel);
    },
  });
}

function openStats() {
  const habits = store.habits();
  openSheet({
    title: t('stats_title'),
    build(body) {
      if (!habits.length) {
        body.appendChild(el('p', 'sheet-message', t('no_habits')));
        return;
      }
      for (const habit of habits) {
        const row = el('div', 'stat-row');
        row.appendChild(el('span', 'stat-name', habit.name));
        const group = store.state.groups[habit.groupId];
        const strip = el('span', 'stat-group');
        strip.style.background = (group && group.color) || '#0078d4';
        row.appendChild(el('span', 'stat-value',
          `📊 ${store.total(habit.id)} ${t('day_unit')}   🔥 ${store.streak(habit.id)} ${t('streak_unit')}`));
        body.appendChild(row);
      }
    },
  });
}

function openSettings() {
  openSheet({
    title: t('settings'),
    build(body, close) {
      const label = el('label', 'field-label', t('token'));
      const input = el('input', 'field-input');
      input.type = 'password';
      input.value = sync.token;
      input.placeholder = 'github_pat_...';
      input.autocomplete = 'off';
      input.spellcheck = false;

      const help = el('p', 'field-help', t('token_help'));
      const status = el('p', 'field-help');

      const save = el('button', 'sheet-item primary', t('save'));
      save.addEventListener('click', () => {
        sync.setToken(input.value);
        status.textContent = t('token_saved');
        status.classList.add('ok-text');
      });

      const test = el('button', 'sheet-item', t('test_connection'));
      test.addEventListener('click', async () => {
        test.disabled = true;
        status.classList.remove('ok-text');
        status.textContent = t('testing');
        try {
          await sync.testConnection(input.value.trim());
          status.textContent = t('connection_ok');
          status.classList.add('ok-text');
        } catch (error) {
          status.textContent = describeError(error);
          status.classList.remove('ok-text');
        } finally {
          test.disabled = false;
        }
      });

      const syncNow = el('button', 'sheet-item', t('sync_now'));
      syncNow.addEventListener('click', () => {
        if (input.value !== sync.token) sync.setToken(input.value);
        sync.run('manual');
        close();
      });

      const forceLabel = el('p', 'field-help');
      forceLabel.textContent = `${t('version')}: ${window.ATM_VERSION || 'dev'}`;
      const force = el('button', 'sheet-item', t('force_update'));
      force.addEventListener('click', () => {
        // Without this, an iOS-cached stale file can waste an hour of
        // debugging on a phone with no devtools.
        if ('serviceWorker' in navigator) {
          navigator.serviceWorker.getRegistrations()
            .then((regs) => Promise.all(regs.map((r) => r.unregister())))
            .then(() => caches.keys())
            .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
            .then(() => window.location.reload(true));
        } else {
          window.location.reload(true);
        }
      });

      const cancel = el('button', 'sheet-item cancel', t('cancel'));
      cancel.addEventListener('click', close);

      body.append(label, input, help, status, save, test, syncNow,
        el('div', 'sheet-separator'), forceLabel, force, cancel);
    },
  });
}

function describeError(error) {
  const kind = error && error.kind;
  if (kind === ErrorKind.AUTH) return t('err_token_invalid');
  if (kind === ErrorKind.FORBIDDEN) return t('err_token_scope');
  if (kind === ErrorKind.RATE_LIMIT) return t('err_rate_limited');
  if (kind === ErrorKind.NETWORK) return t('err_network');
  if (kind === ErrorKind.CONFLICT) return t('err_conflict_retry');
  return t('err_unknown', { msg: (error && error.message) || String(error) });
}

// ── Render orchestration ─────────────────────────────────────────────────

function renderAll() {
  t = makeT(store.lang);
  document.title = t('title');
  refs.title.textContent = t('title');
  refs.langBtn.textContent = t('lang');
  renderWeekNav();
  renderList();
  renderFooter();
}

/**
 * Everything that, when it changes, requires rebuilding the DOM.
 *
 * Deliberately excludes check-ins, which are the one thing that changes dozens
 * of times a day and must not tear down the element the user just tapped.
 */
function structureSignature() {
  return JSON.stringify({
    lang: store.lang,
    week: store.weekRef,
    selected: store.selectedDate,
    collapsed: [...store.collapsed],
    groups: store.groups().map((g) => [g.id, g.name_zh, g.name_en, g.color, g.order]),
    habits: store.habits().map((h) => [h.id, h.name, h.groupId, h.order]),
  });
}

function onStoreChange() {
  const allDone = store.allDoneOn(store.selectedDate);
  // Celebrate only on the transition, and only for today or the past --
  // pre-checking a future day should not fire it.
  if (allDone && lastAllDone === false && store.selectedDate <= todayStr()) {
    toast(t('all_done'));
  }
  lastAllDone = allDone;

  const signature = structureSignature();
  if (signature !== lastSignature) {
    lastSignature = signature;
    renderAll();
    return;
  }

  // Nothing structural changed, so repaint in place. A full rebuild here would
  // replace the circle mid-tap and kill its transition, and would make the
  // stats toggle flicker on every check-in.
  for (const row of refs.list.querySelectorAll('.row')) paintRow(row);
  paintWeekNav();
  renderFooter();
}

function onSyncChange() {
  paintSyncDot();
  if (sync.status === SyncStatus.ERROR && sync.lastError
    && sync.lastError.kind === ErrorKind.AUTH) {
    // A dead token needs the user; anything else retries itself.
    toast(t('err_token_invalid'), { actionLabel: t('settings'), onAction: openSettings });
  }
}

export function mount(container) {
  buildShell(container);
  store.subscribe(onStoreChange);
  sync.subscribe(onSyncChange);
  renderAll();
  lastSignature = structureSignature();
  lastAllDone = store.allDoneOn(store.selectedDate);
  return { renderAll };
}
