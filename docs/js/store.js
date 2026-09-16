/**
 * Application state: persistence, mutations, local preferences.
 *
 * Two storage layers, deliberately separated:
 *
 *   synced   -> the state document (habits, groups, check-ins). Goes to GitHub.
 *   local    -> deviceId, token, language, selected date, collapsed groups.
 *
 * Nothing in the `local` layer may leak into the synced one. `collapsed` is
 * the trap: if it were synced, collapsing a group on the phone would revert a
 * group rename made on the desktop, because whole-record last-write-wins
 * cannot tell "hide this row" from "rename this row".
 */

import {
  applyCheckin, checkedDates, emptyState, isChecked, liveRecords,
  mergeStates, normalizeState, pruneTombstones, stableStringify, touchRecord,
} from './merge.js';

const K = {
  state: 'atm.state',
  sha: 'atm.sha',
  dirty: 'atm.dirty',
  device: 'atm.device',
  lang: 'atm.lang',
  selected: 'atm.selectedDate',
  collapsed: 'atm.collapsed',
  backupPrefix: 'atm.backup.',
};

const MAX_BACKUPS = 3;

// ── Time ─────────────────────────────────────────────────────────────────
// Beijing everywhere, matching tools/send_report.py. The user is in China and
// a mismatch between what the app calls "today" and what the 06:05 report
// calls "today" would be baffling. ONE place to change if that ever stops
// being true.

const BJ_OFFSET_MS = 8 * 3600 * 1000;

/** Current time shifted so that UTC getters read as Beijing wall clock. */
function bjShifted(now = Date.now()) {
  return new Date(now + BJ_OFFSET_MS);
}

export function todayStr(now = Date.now()) {
  return bjShifted(now).toISOString().slice(0, 10);
}

export function nowSec() {
  return Math.floor(Date.now() / 1000);
}

/** 'HH:MM' in Beijing, for commit messages read during debugging. */
export function nowTimeStr(now = Date.now()) {
  return bjShifted(now).toISOString().slice(11, 16);
}

/** 'YYYY-MM-DD' -> Date at Beijing midnight (as a shifted Date). */
export function parseDate(dateStr) {
  return new Date(`${dateStr}T00:00:00.000Z`);
}

export function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

/** Monday-start week containing `dateStr`. */
export function weekDates(dateStr) {
  const base = parseDate(dateStr);
  const weekday = (base.getUTCDay() + 6) % 7; // Mon = 0
  const monday = new Date(base);
  monday.setUTCDate(monday.getUTCDate() - weekday);
  return Array.from({ length: 7 }, (_, i) => {
    const day = new Date(monday);
    day.setUTCDate(monday.getUTCDate() + i);
    return formatDate(day);
  });
}

/** Shift a date string by whole days. */
export function addDays(dateStr, days) {
  const date = parseDate(dateStr);
  date.setUTCDate(date.getUTCDate() + days);
  return formatDate(date);
}

export function currentCycleKey(cycle, dateStr = todayStr()) {
  const date = parseDate(dateStr);
  if (cycle === 'weekly') {
    const thursday = new Date(date); // ISO weeks belong to the year of their Thursday
    thursday.setUTCDate(date.getUTCDate() + 3 - ((date.getUTCDay() + 6) % 7));
    const firstThursday = new Date(Date.UTC(thursday.getUTCFullYear(), 0, 4));
    firstThursday.setUTCDate(
      firstThursday.getUTCDate() + 3 - ((firstThursday.getUTCDay() + 6) % 7));
    const week = 1 + Math.round((thursday - firstThursday) / (7 * 86400000));
    return `${thursday.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
  }
  if (cycle === 'monthly') return dateStr.slice(0, 7);
  return dateStr;
}

// ── Store ────────────────────────────────────────────────────────────────

function readJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

class Store {
  constructor() {
    this.state = emptyState();
    this.sha = null;
    this.dirty = false;
    this.deviceId = '';
    this.lang = 'zh';
    this.selectedDate = todayStr();
    this.weekRef = this.selectedDate;
    this.collapsed = new Set();
    this.lastSyncAt = 0;
    this.syncError = null;
    this.listeners = new Set();
  }

  // ── lifecycle ──
  load() {
    this.state = normalizeState(readJSON(K.state, emptyState()));
    this.sha = localStorage.getItem(K.sha) || null;
    this.dirty = localStorage.getItem(K.dirty) === '1';
    this.deviceId = localStorage.getItem(K.device) || '';
    if (!this.deviceId) {
      this.deviceId = `dev-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(K.device, this.deviceId);
      this.dirty = true; // a fresh device has never pushed
    }
    const lang = localStorage.getItem(K.lang);
    if (lang === 'zh' || lang === 'en') this.lang = lang;
    const selected = localStorage.getItem(K.selected);
    if (selected) {
      this.selectedDate = selected;
      this.weekRef = selected;
    }
    const collapsed = readJSON(K.collapsed, []);
    this.collapsed = new Set(Array.isArray(collapsed) ? collapsed : []);
    return this;
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  emit() {
    for (const fn of this.listeners) fn(this);
  }

  persist() {
    try {
      localStorage.setItem(K.state, stableStringify(this.state));
      localStorage.setItem(K.dirty, this.dirty ? '1' : '0');
      if (this.sha) localStorage.setItem(K.sha, this.sha);
    } catch (error) {
      // Quota exceeded. The backup ring is the usual culprit; drop it rather
      // than let a check-in silently fail to persist.
      console.warn('persist failed, clearing backups', error);
      this._clearBackups();
      try {
        localStorage.setItem(K.state, stableStringify(this.state));
      } catch { /* give up; sync will still carry the data */ }
    }
  }

  /** Snapshot before a push, so a bad merge is recoverable without a computer. */
  backup() {
    try {
      localStorage.setItem(
        `${K.backupPrefix}${Date.now()}`,
        stableStringify({ sha: this.sha, state: this.state }));
      const keys = Object.keys(localStorage)
        .filter((k) => k.startsWith(K.backupPrefix)).sort();
      for (const key of keys.slice(0, Math.max(0, keys.length - MAX_BACKUPS))) {
        localStorage.removeItem(key);
      }
    } catch { /* backups are best-effort */ }
  }

  _clearBackups() {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(K.backupPrefix)) localStorage.removeItem(key);
    }
  }

  setLang(lang) {
    this.lang = lang;
    localStorage.setItem(K.lang, lang);
    this.emit();
  }

  setSelectedDate(dateStr) {
    this.selectedDate = dateStr;
    localStorage.setItem(K.selected, dateStr);
    this.emit();
  }

  setWeekRef(dateStr) {
    this.weekRef = dateStr;
    // Paging must move the selection into the visible week. The desktop app
    // left selectedDate pointing at the old week, so tapping a circle silently
    // edited a different day and no date appeared selected at all.
    if (!weekDates(this.weekRef).includes(this.selectedDate)) {
      const today = todayStr();
      this.selectedDate = weekDates(this.weekRef).includes(today)
        ? today : weekDates(this.weekRef)[0];
      localStorage.setItem(K.selected, this.selectedDate);
    }
    this.emit();
  }

  toggleCollapsed(groupId) {
    if (this.collapsed.has(groupId)) this.collapsed.delete(groupId);
    else this.collapsed.add(groupId);
    localStorage.setItem(K.collapsed, JSON.stringify([...this.collapsed]));
    this.emit();
  }

  /** Replace state with a merge result and record whether it still needs a push. */
  adopt(merged, cloudText) {
    this.state = normalizeState(merged);
    this.dirty = stableStringify(this.state) !== cloudText;
    if (!this.dirty) this.sha = this.sha; // unchanged
    this.persist();
    this.emit();
  }

  mergeIn(incoming) {
    this.state = mergeStates(this.state, incoming);
    this.dirty = true;
    this.persist();
    this.emit();
  }

  // ── reads ──
  groups() {
    return liveRecords(this.state.groups).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  }

  habits() {
    return liveRecords(this.state.habits).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  }

  habitsInGroup(groupId) {
    return this.habits().filter((h) => h.groupId === groupId);
  }

  groupName(groupId) {
    const group = this.state.groups[groupId];
    if (!group || group.deleted) return '';
    return this.lang === 'en'
      ? (group.name_en || group.name_zh)
      : (group.name_zh || group.name_en);
  }

  isChecked(habitId, dateStr = this.selectedDate) {
    return isChecked(this.state, habitId, dateStr);
  }

  total(habitId) {
    return checkedDates(this.state, habitId).length;
  }

  /**
   * Consecutive days ending today.
   *
   * Anchored at yesterday when today is unchecked: the desktop version
   * anchored at today and so reported 0 every morning until you checked in,
   * which reads as "your streak broke" rather than "you haven't started yet".
   */
  streak(habitId) {
    const checked = new Set(checkedDates(this.state, habitId));
    const today = todayStr();
    let cursor = checked.has(today) ? today : addDays(today, -1);
    let count = 0;
    while (checked.has(cursor)) {
      count++;
      cursor = addDays(cursor, -1);
    }
    return count;
  }

  /** True when every current habit has a check-in on `dateStr`. */
  allDoneOn(dateStr) {
    const habits = this.habits();
    if (!habits.length) return false;
    return habits.every((h) => isChecked(this.state, h.id, dateStr));
  }

  /**
   * Percentage of check-ins completed over the elapsed days of this week.
   *
   * The desktop version divided by a full 7 days including the future, so a
   * perfect Monday scored 14%.
   */
  weekCompletionRate(refDateStr = todayStr()) {
    const habits = this.habits();
    if (!habits.length) return 0;
    const today = todayStr();
    const elapsed = weekDates(refDateStr).filter((d) => d <= today);
    if (!elapsed.length) return 0;
    let done = 0;
    for (const day of elapsed) {
      done += habits.filter((h) => isChecked(this.state, h.id, day)).length;
    }
    return Math.round((done / (elapsed.length * habits.length)) * 100);
  }

  // ── mutations ──
  // Each records a full updated record (invariant I2) with a bumped updatedAt
  // (invariant I1), then marks the store dirty for the next sync.

  _touch(record) {
    touchRecord(record, nowSec(), this.deviceId);
    this.dirty = true;
  }

  _commit() {
    this.persist();
    this.emit();
  }

  toggleCheckin(habitId, dateStr = this.selectedDate) {
    const next = !this.isChecked(habitId, dateStr);
    applyCheckin(this.state, habitId, dateStr, next, nowSec());
    this.dirty = true;
    this._commit();
    return next;
  }

  addHabit(name, groupId) {
    const trimmed = String(name || '').trim();
    if (!trimmed) return null;
    const id = `h_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    const siblings = this.habitsInGroup(groupId);
    const last = siblings[siblings.length - 1];
    this.state.habits[id] = {
      id, name: trimmed, groupId,
      order: last ? (last.order ?? 0) + 10 : 0,
      deleted: false,
    };
    this._touch(this.state.habits[id]);
    this._commit();
    return id;
  }

  editHabit(id, { name, groupId }) {
    const habit = this.state.habits[id];
    if (!habit || habit.deleted) return;
    const trimmed = String(name || '').trim();
    if (!trimmed) return;
    if (groupId && groupId !== habit.groupId) {
      const siblings = this.habitsInGroup(groupId);
      const last = siblings[siblings.length - 1];
      habit.order = last ? (last.order ?? 0) + 10 : 0;
    }
    habit.name = trimmed;
    if (groupId) habit.groupId = groupId;
    this._touch(habit);
    this._commit();
  }

  deleteHabit(id) {
    const habit = this.state.habits[id];
    if (!habit) return null;
    const snapshot = { ...habit };
    habit.deleted = true;
    this._touch(habit);
    this._commit();
    return snapshot; // caller shows an undo affordance
  }

  /** Swap a habit with its neighbour within its own group. */
  moveHabit(id, delta) {
    const habit = this.state.habits[id];
    if (!habit || habit.deleted) return false;
    const siblings = this.habitsInGroup(habit.groupId);
    const index = siblings.findIndex((h) => h.id === id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= siblings.length) return false;

    // Renumber the whole group from the new sequence and touch only the
    // records whose order actually changed, to keep the diff small.
    const reordered = [...siblings];
    reordered.splice(index, 1);
    reordered.splice(target, 0, habit);
    reordered.forEach((item, position) => {
      const order = position * 10;
      if ((item.order ?? 0) !== order) {
        item.order = order;
        this._touch(item);
      }
    });
    this._commit();
    return true;
  }

  moveHabitToGroup(id, groupId) {
    const habit = this.state.habits[id];
    if (!habit || habit.deleted || habit.groupId === groupId) return;
    const siblings = this.habitsInGroup(groupId);
    const last = siblings[siblings.length - 1];
    habit.groupId = groupId;
    habit.order = last ? (last.order ?? 0) + 10 : 0;
    this._touch(habit);
    this._commit();
  }

  addGroup(nameZh, nameEn, color) {
    const zh = String(nameZh || '').trim();
    if (!zh) return null;
    const id = `g_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    const order = this.groups().reduce((max, g) => Math.max(max, g.order ?? 0), -10) + 10;
    this.state.groups[id] = {
      id, name_zh: zh, name_en: String(nameEn || '').trim() || zh,
      color: color || '#0078d4', order, deleted: false,
    };
    this._touch(this.state.groups[id]);
    this._commit();
    return id;
  }

  editGroup(id, { nameZh, nameEn, color }) {
    const group = this.state.groups[id];
    if (!group || group.deleted) return;
    const zh = String(nameZh || '').trim();
    if (!zh) return;
    group.name_zh = zh;
    group.name_en = String(nameEn || '').trim() || zh;
    if (color) group.color = color;
    this._touch(group);
    this._commit();
  }

  /** Deletes the group AND its habits, matching the desktop confirmation text. */
  deleteGroup(id) {
    const group = this.state.groups[id];
    if (!group) return null;
    const orphans = this.habitsInGroup(id);
    for (const habit of orphans) {
      habit.deleted = true;
      this._touch(habit);
    }
    group.deleted = true;
    this._touch(group);
    this.collapsed.delete(id);
    localStorage.setItem(K.collapsed, JSON.stringify([...this.collapsed]));
    this._commit();
    return { group: { ...group }, habits: orphans.map((h) => ({ ...h })) };
  }

  prune() {
    pruneTombstones(this.state, nowSec());
  }
}

export const store = new Store().load();
