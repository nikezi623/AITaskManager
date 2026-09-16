/**
 * Bootstrap.
 *
 * Kept deliberately thin: mount the UI, start the sync triggers, register the
 * service worker. All the interesting logic lives in the modules it imports.
 */

import { mount } from './ui.js';
import { primeAudio } from './gestures.js';
import { sync } from './sync.js';
import { store } from './store.js';

// Bump together with CACHE_VERSION in ../sw.js.
const VERSION = '2026-09-16.1';
window.ATM_VERSION = VERSION;

function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('./sw.js', { updateViaCache: 'none' })
    .then((registration) => {
      // Check for a new build whenever the app comes back to the foreground --
      // a PWA can stay resident for days without ever re-fetching index.html.
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') registration.update().catch(() => {});
      });
    })
    .catch((error) => console.warn('SW registration failed', error));

  // Reload once when a new worker takes over, guarded so it cannot loop.
  let reloading = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading) return;
    reloading = true;
    window.location.reload();
  });
}

function boot() {
  mount(document.getElementById('app'));

  // iOS suspends an AudioContext created outside a user gesture, so the
  // check-in click would be silent on the very first tap.
  const unlock = () => {
    primeAudio();
    document.removeEventListener('pointerdown', unlock);
  };
  document.addEventListener('pointerdown', unlock);

  sync.start();
  registerServiceWorker();

  if (!sync.hasToken) {
    // First run: nothing to sync yet, and the settings sheet explains the token.
    console.info('ATM: no token configured. Open Settings to connect the data repo.');
  } else if (store.dirty) {
    sync.schedule('boot-dirty', 0);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
