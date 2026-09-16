/**
 * Pull-merge-push orchestration.
 *
 * iOS has no Background Sync, so every sync is foreground-triggered. The
 * `visibilitychange` trigger is therefore not a nicety -- it is the mechanism
 * by which an edit made on the desktop reaches the phone.
 *
 * Rule that governs every error path here: NEVER clear or reset local state.
 * A failed push means "try again later", never "lose what the user did".
 */

import { mergeStates, normalizeState, stableStringify } from './merge.js';
import { ErrorKind, GitHubError, getFile, putFile } from './github.js';
import { store, todayStr } from './store.js';

const TOKEN_KEY = 'atm.token';
const CONFLICT_ATTEMPTS = 3;
const PUSH_DEBOUNCE_MS = 2000;
const DIRTY_POLL_MS = 60000;
const BACKOFF_MS = [10000, 30000, 60000];

export const SyncStatus = {
  IDLE: 'idle',
  SYNCING: 'syncing',
  OFFLINE: 'offline',
  ERROR: 'error',
};

class Sync {
  constructor() {
    this.token = localStorage.getItem(TOKEN_KEY) || '';
    this.status = SyncStatus.IDLE;
    this.lastError = null;    // { kind, message }
    this.lastSyncAt = 0;
    this.listeners = new Set();
    this.pushTimer = null;
    this.retryTimer = null;
    this.retryIndex = 0;
    this.running = false;
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  emit() {
    for (const fn of this.listeners) fn(this);
  }

  get hasToken() {
    return Boolean(this.token);
  }

  setToken(token) {
    this.token = String(token || '').trim();
    if (this.token) localStorage.setItem(TOKEN_KEY, this.token);
    else localStorage.removeItem(TOKEN_KEY);
    this.retryIndex = 0;
    this.emit();
    if (this.token) this.schedule('token-set', 0);
  }

  /** Surfaces a typed error to the UI without disturbing local data. */
  _fail(error) {
    if (error instanceof GitHubError) {
      this.lastError = { kind: error.kind, message: error.message };
      if (error.kind === ErrorKind.NETWORK) this.status = SyncStatus.OFFLINE;
      else if (error.kind === ErrorKind.RATE_LIMIT) this.status = SyncStatus.OFFLINE;
      else this.status = SyncStatus.ERROR;
    } else {
      this.lastError = { kind: ErrorKind.UNKNOWN, message: String(error) };
      this.status = SyncStatus.ERROR;
    }
    this.emit();
  }

  /** Queue a sync, coalescing bursts of edits into one push. */
  schedule(reason, delay = PUSH_DEBOUNCE_MS) {
    if (!this.hasToken) return;
    if (this.pushTimer) clearTimeout(this.pushTimer);
    this.pushTimer = setTimeout(() => {
      this.pushTimer = null;
      this.run(reason);
    }, delay);
  }

  _scheduleRetry() {
    if (!this.hasToken) return;
    const delay = BACKOFF_MS[Math.min(this.retryIndex, BACKOFF_MS.length - 1)];
    this.retryIndex++;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.run('retry');
    }, delay);
  }

  /**
   * One pull-merge-push cycle.
   *
   * A 409 is the expected path when both devices are active, not an error: it
   * means the sha moved, so re-pull and merge (idempotent, so the result is
   * identical) and push again.
   */
  async run(reason = 'manual') {
    if (!this.hasToken || this.running) return false;
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      this.status = SyncStatus.OFFLINE;
      this.lastError = { kind: ErrorKind.NETWORK, message: 'offline' };
      this.emit();
      return false;
    }

    this.running = true;
    this.status = SyncStatus.SYNCING;
    this.emit();

    try {
      for (let attempt = 0; attempt < CONFLICT_ATTEMPTS; attempt++) {
        const cloud = await getFile(this.token);
        const cloudState = cloud.text ? normalizeState(JSON.parse(cloud.text)) : null;

        const merged = cloudState ? mergeStates(cloudState, store.state) : store.state;
        const mergedText = stableStringify(merged);
        const cloudText = cloudState ? stableStringify(cloudState) : null;

        let sha = cloud.sha;
        if (!cloudState || mergedText !== cloudText) {
          // Snapshot before pushing: this is the recovery path if a merge ever
          // does something surprising, and it needs no computer.
          store.backup();
          const message = `sync ${store.deviceId} ${todayStr()} ${new Date().toISOString().slice(11, 16)}Z`;
          const result = await putFile(this.token, mergedText, cloud.sha, message);
          sha = result.sha;
        }

        // Merge rather than assign: a check-in tapped while the request was in
        // flight is in store.state but not in `merged`, and assigning would
        // silently discard it.
        const next = mergeStates(merged, store.state);
        const nextText = stableStringify(next);

        store.state = next;
        store.sha = sha;
        store.dirty = nextText !== mergedText;
        store.persist();

        this.status = SyncStatus.IDLE;
        this.lastError = null;
        this.lastSyncAt = Date.now();
        this.retryIndex = 0;
        this.running = false;
        store.emit();
        this.emit();

        if (store.dirty) this.schedule('post-sync-local-changes');
        return true;
      }

      // Exhausted attempts: another device is writing continuously.
      this.running = false;
      this._fail(new GitHubError(ErrorKind.CONFLICT, 'gave up after retries'));
      this._scheduleRetry();
      return false;
    } catch (error) {
      this.running = false;
      this._fail(error);
      if (error instanceof GitHubError && error.kind === ErrorKind.CONFLICT) {
        this._scheduleRetry();
      } else if (!(error instanceof GitHubError)
        || (error.kind !== ErrorKind.AUTH && error.kind !== ErrorKind.FORBIDDEN)) {
        this._scheduleRetry();
      }
      return false;
    }
  }

  /** Verify the token and repo access without touching data. */
  async testConnection(token = this.token) {
    if (!token) throw new GitHubError(ErrorKind.AUTH, 'no token');
    await getFile(token);
    return true;
  }

  /** Install foreground triggers. Called once at boot. */
  start() {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
          if (store.dirty) this.schedule('visible', 0);
          else this.run('visible-idle'); // cheap pull so desktop edits land
        }
      });
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => this.schedule('online', 0));
      window.addEventListener('offline', () => {
        this.status = SyncStatus.OFFLINE;
        this.emit();
      });
    }
    // Poll while dirty: covers the case where the user keeps the app open and
    // a previous push failed for a transient reason.
    setInterval(() => {
      if (store.dirty && !this.running) this.schedule('dirty-poll', 0);
    }, DIRTY_POLL_MS);
    this.run('boot');
  }
}

export const sync = new Sync();
