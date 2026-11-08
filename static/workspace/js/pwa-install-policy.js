/**
 * Pure policy helpers for workspace PWA install suggestion.
 * Usable in browser and Node (no DOM dependency).
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.wsPwaInstallPolicy = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var STORAGE_DISMISS_UNTIL = 'ws-pwa-suggest-dismiss-until';
  var STORAGE_INSTALLED = 'ws-pwa-installed';
  var DISMISS_DAYS = 7;
  var DISMISS_MS = DISMISS_DAYS * 24 * 60 * 60 * 1000;
  var SUGGEST_DELAY_MS = 1800;
  var SUGGEST_RETRY_MS = 2000;
  var SUGGEST_MAX_WAIT_MS = 45000;

  function isMobileUa(ua) {
    var s = String(ua || '');
    if (/Android|iPhone|iPad|iPod|Mobile/i.test(s)) return true;
    // iPadOS 13+ desktop UA still has Macintosh + touch
    if (/Macintosh/i.test(s) && /Mobile/i.test(s)) return true;
    return false;
  }

  function readDismissUntil(storageGetItem) {
    try {
      var raw = storageGetItem(STORAGE_DISMISS_UNTIL);
      if (!raw) return 0;
      var n = parseInt(raw, 10);
      return isNaN(n) ? 0 : n;
    } catch (e) {
      return 0;
    }
  }

  function isDismissed(now, storageGetItem) {
    var until = readDismissUntil(storageGetItem);
    return until > now;
  }

  function isMarkedInstalled(storageGetItem) {
    try {
      return storageGetItem(STORAGE_INSTALLED) === '1';
    } catch (e) {
      return false;
    }
  }

  function dismissUntilTimestamp(now) {
    return now + DISMISS_MS;
  }

  /**
   * Decide whether the automatic install suggestion modal may open.
   * System Chrome prompt must still require a user gesture; this only gates our modal.
   */
  function shouldAutoSuggest(opts) {
    opts = opts || {};
    if (opts.isStandalone) return false;
    if (!opts.isMobile) return false;
    if (!opts.hasDeferredPrompt) return false;
    if (opts.isMarkedInstalled) return false;
    if (opts.isDismissed) return false;
    if (opts.hasBlockingUi) return false;
    if (opts.alreadyShownThisSession) return false;
    return true;
  }

  return {
    STORAGE_DISMISS_UNTIL: STORAGE_DISMISS_UNTIL,
    STORAGE_INSTALLED: STORAGE_INSTALLED,
    DISMISS_DAYS: DISMISS_DAYS,
    DISMISS_MS: DISMISS_MS,
    SUGGEST_DELAY_MS: SUGGEST_DELAY_MS,
    SUGGEST_RETRY_MS: SUGGEST_RETRY_MS,
    SUGGEST_MAX_WAIT_MS: SUGGEST_MAX_WAIT_MS,
    isMobileUa: isMobileUa,
    readDismissUntil: readDismissUntil,
    isDismissed: isDismissed,
    isMarkedInstalled: isMarkedInstalled,
    dismissUntilTimestamp: dismissUntilTimestamp,
    shouldAutoSuggest: shouldAutoSuggest,
  };
});
