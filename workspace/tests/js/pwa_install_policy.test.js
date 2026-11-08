'use strict';

const assert = require('assert');
const path = require('path');
const policy = require(path.resolve(
  __dirname,
  '../../../static/workspace/js/pwa-install-policy.js'
));

function store(map) {
  return {
    get: (k) => (Object.prototype.hasOwnProperty.call(map, k) ? map[k] : null),
    set: (k, v) => { map[k] = String(v); },
  };
}

function run() {
  assert.strictEqual(policy.DISMISS_DAYS, 7);
  assert.ok(policy.isMobileUa('Mozilla/5.0 (Linux; Android 14; Pixel) Chrome/120.0.0.0 Mobile Safari/537.36'));
  assert.ok(policy.isMobileUa('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'));
  assert.strictEqual(policy.isMobileUa('Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'), false);

  const now = 1_700_000_000_000;
  const map = {};
  const s = store(map);
  assert.strictEqual(policy.isDismissed(now, s.get), false);
  map[policy.STORAGE_DISMISS_UNTIL] = String(policy.dismissUntilTimestamp(now));
  assert.strictEqual(policy.isDismissed(now + 1000, s.get), true);
  assert.strictEqual(policy.isDismissed(now + policy.DISMISS_MS + 1, s.get), false);

  assert.strictEqual(policy.isMarkedInstalled(s.get), false);
  map[policy.STORAGE_INSTALLED] = '1';
  assert.strictEqual(policy.isMarkedInstalled(s.get), true);

  assert.strictEqual(
    policy.shouldAutoSuggest({
      isStandalone: false,
      isMobile: true,
      hasDeferredPrompt: true,
      isMarkedInstalled: false,
      isDismissed: false,
      hasBlockingUi: false,
      alreadyShownThisSession: false,
    }),
    true
  );

  assert.strictEqual(
    policy.shouldAutoSuggest({
      isStandalone: true,
      isMobile: true,
      hasDeferredPrompt: true,
      isMarkedInstalled: false,
      isDismissed: false,
      hasBlockingUi: false,
      alreadyShownThisSession: false,
    }),
    false,
    'standalone must hide suggest'
  );

  assert.strictEqual(
    policy.shouldAutoSuggest({
      isStandalone: false,
      isMobile: false,
      hasDeferredPrompt: true,
      isMarkedInstalled: false,
      isDismissed: false,
      hasBlockingUi: false,
      alreadyShownThisSession: false,
    }),
    false,
    'desktop must hide auto suggest'
  );

  assert.strictEqual(
    policy.shouldAutoSuggest({
      isStandalone: false,
      isMobile: true,
      hasDeferredPrompt: false,
      isMarkedInstalled: false,
      isDismissed: false,
      hasBlockingUi: false,
      alreadyShownThisSession: false,
    }),
    false,
    'without beforeinstallprompt do not auto-show'
  );

  assert.strictEqual(
    policy.shouldAutoSuggest({
      isStandalone: false,
      isMobile: true,
      hasDeferredPrompt: true,
      isMarkedInstalled: false,
      isDismissed: true,
      hasBlockingUi: false,
      alreadyShownThisSession: false,
    }),
    false,
    'dismissed for 7 days'
  );

  assert.strictEqual(
    policy.shouldAutoSuggest({
      isStandalone: false,
      isMobile: true,
      hasDeferredPrompt: true,
      isMarkedInstalled: false,
      isDismissed: false,
      hasBlockingUi: true,
      alreadyShownThisSession: false,
    }),
    false,
    'blocking modal'
  );

  assert.strictEqual(
    policy.shouldAutoSuggest({
      isStandalone: false,
      isMobile: true,
      hasDeferredPrompt: true,
      isMarkedInstalled: true,
      isDismissed: false,
      hasBlockingUi: false,
      alreadyShownThisSession: false,
    }),
    false,
    'already installed'
  );

  console.log('pwa_install_policy.test.js: OK');
}

run();
