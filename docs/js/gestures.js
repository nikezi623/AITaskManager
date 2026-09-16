/**
 * Touch interaction primitives.
 *
 * Replaces two desktop idioms that do not exist on iOS:
 *   - check-in on mousePressEvent  -> tap (click), so the browser's own tap
 *     detection does the scroll-vs-tap discrimination for us
 *   - Qt.CustomContextMenu         -> 500ms long-press
 *
 * Haptics are not available: `navigator.vibrate` is unimplemented in iOS
 * Safari and in standalone PWAs, and no web API reaches the Taptic Engine.
 * A short click via WebAudio plus a CSS transition stands in.
 */

const LONG_PRESS_MS = 500;
const MOVE_TOLERANCE_PX = 10;

/**
 * Fire `handler` after a stationary long press.
 *
 * Cancels on movement, pointercancel and pointerup -- on a scrolling list an
 * uncancelled long-press timer is a guaranteed misfire.
 */
export function onLongPress(element, handler, { delay = LONG_PRESS_MS } = {}) {
  let timer = null;
  let startX = 0;
  let startY = 0;

  const cancel = () => {
    if (timer) clearTimeout(timer);
    timer = null;
  };

  element.addEventListener('pointerdown', (event) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    startX = event.clientX;
    startY = event.clientY;
    cancel();
    timer = setTimeout(() => {
      timer = null;
      handler(event);
    }, delay);
  });

  element.addEventListener('pointermove', (event) => {
    if (!timer) return;
    if (Math.hypot(event.clientX - startX, event.clientY - startY) > MOVE_TOLERANCE_PX) cancel();
  });
  element.addEventListener('pointerup', cancel);
  element.addEventListener('pointercancel', cancel);
  element.addEventListener('pointerleave', cancel);

  return cancel;
}

/** Suppress the iOS selection callout / context menu on a container. */
export function suppressCallout(element) {
  element.addEventListener('contextmenu', (event) => event.preventDefault());
  return element;
}

// ── Haptics substitute ───────────────────────────────────────────────────

let audioContext = null;

/**
 * Unlock audio on the first user gesture.
 *
 * iOS suspends an AudioContext created outside a gesture, so the very first
 * tap would be silent without this.
 */
export function primeAudio() {
  if (audioContext) return;
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return;
  try {
    audioContext = new Ctor();
    if (audioContext.state === 'suspended') audioContext.resume();
  } catch { /* audio is a nicety, never a requirement */ }
}

/** A 12ms click. Stands in for the haptic iOS will not give us. */
export function tick(checked) {
  if (!audioContext) return;
  try {
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const now = audioContext.currentTime;
    oscillator.frequency.value = checked ? 880 : 520;
    gain.gain.setValueAtTime(0.06, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.012);
    oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.012);
  } catch { /* ignore */ }
}

// ── Bottom sheet ─────────────────────────────────────────────────────────

let activeSheet = null;

/**
 * Open a bottom sheet. Returns a close() function.
 *
 * Sheets rather than centred modals: thumb-reachable, and they sidestep the
 * iOS keyboard/viewport-resize problem entirely.
 */
export function openSheet({ title, build, onClose } = {}) {
  closeSheet();

  const backdrop = document.createElement('div');
  backdrop.className = 'sheet-backdrop';

  const sheet = document.createElement('div');
  sheet.className = 'sheet';
  sheet.setAttribute('role', 'dialog');

  const close = () => {
    if (activeSheet !== sheet) return;
    activeSheet = null;
    backdrop.classList.remove('open');
    sheet.classList.remove('open');
    // A sheet fades out over 200ms. Without this it stays clickable during the
    // fade, so a fast tap can hit a button on a sheet the user already
    // dismissed -- or on the previous sheet when one replaces another.
    sheet.classList.add('closing');
    setTimeout(() => {
      backdrop.remove();
      sheet.remove();
    }, 200);
    if (onClose) onClose();
  };

  backdrop.addEventListener('click', close);

  if (title) {
    const heading = document.createElement('div');
    heading.className = 'sheet-title';
    heading.textContent = title;
    sheet.appendChild(heading);
  }

  const body = document.createElement('div');
  body.className = 'sheet-body';
  sheet.appendChild(body);
  if (build) build(body, close);

  document.body.appendChild(backdrop);
  document.body.appendChild(sheet);
  activeSheet = sheet;

  requestAnimationFrame(() => {
    backdrop.classList.add('open');
    sheet.classList.add('open');
  });
  return close;
}

export function closeSheet() {
  const sheet = document.querySelector('.sheet.open');
  const backdrop = document.querySelector('.sheet-backdrop.open');
  if (backdrop) backdrop.click();
  else if (sheet) sheet.remove();
}

/** A list of actions, each closing the sheet before running. */
export function showMenu(items, { title, cancelLabel = '取消' } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    // Settle BEFORE closing. close() fires onClose, which resolves null, and a
    // promise can only settle once -- so closing first makes every selection a
    // no-op. The guard makes the ordering mistake impossible to reintroduce.
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    openSheet({
      title,
      build(body, close) {
        for (const item of items) {
          if (item.separator) {
            const rule = document.createElement('div');
            rule.className = 'sheet-separator';
            body.appendChild(rule);
            continue;
          }
          const button = document.createElement('button');
          button.className = `sheet-item${item.danger ? ' danger' : ''}`;
          button.textContent = item.label;
          button.addEventListener('click', () => {
            finish(item);
            close();
            if (item.onSelect) item.onSelect();
          });
          body.appendChild(button);
        }
        const cancel = document.createElement('button');
        cancel.className = 'sheet-item cancel';
        cancel.textContent = cancelLabel;
        cancel.addEventListener('click', () => {
          finish(null);
          close();
        });
        body.appendChild(cancel);
      },
      onClose: () => finish(null),
    });
  });
}

export function showConfirm({ title, message, confirmLabel = '确定', cancelLabel = '取消', danger } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    openSheet({
      title,
      build(body, close) {
        if (message) {
          const text = document.createElement('p');
          text.className = 'sheet-message';
          text.textContent = message;
          body.appendChild(text);
        }
        // Same ordering rule as showMenu: settle first, then close.
        const confirm = document.createElement('button');
        confirm.className = `sheet-item${danger ? ' danger' : ''}`;
        confirm.textContent = confirmLabel;
        confirm.addEventListener('click', () => {
          finish(true);
          close();
        });
        const cancel = document.createElement('button');
        cancel.className = 'sheet-item cancel';
        cancel.textContent = cancelLabel;
        cancel.addEventListener('click', () => {
          finish(false);
          close();
        });
        body.appendChild(confirm);
        body.appendChild(cancel);
      },
      onClose: () => finish(false),
    });
  });
}

/** Transient message with an optional single action (used for undo). */
export function toast(message, { actionLabel, onAction, duration = 4000 } = {}) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const element = document.createElement('div');
  element.className = 'toast';
  const text = document.createElement('span');
  text.textContent = message;
  element.appendChild(text);

  let timer = null;
  const dismiss = () => {
    if (timer) clearTimeout(timer);
    element.classList.remove('open');
    setTimeout(() => element.remove(), 200);
  };

  if (actionLabel) {
    const action = document.createElement('button');
    action.className = 'toast-action';
    action.textContent = actionLabel;
    action.addEventListener('click', () => {
      dismiss();
      if (onAction) onAction();
    });
    element.appendChild(action);
  }

  document.body.appendChild(element);
  requestAnimationFrame(() => element.classList.add('open'));
  timer = setTimeout(dismiss, duration);
  return dismiss;
}
