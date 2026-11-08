/**
 * Workspace PWA client — install prompt, auto mobile suggest, SW lifecycle, offline banner.
 * System install prompt is only opened from a user click (never auto).
 */
(function () {
  'use strict';

  var SW_URL = '/workspace/sw.js';
  var policy = window.wsPwaInstallPolicy || {};
  var deferredPrompt = null;
  var registration = null;
  var formDirty = false;
  var updateBannerEl = null;
  var suggestShownThisSession = false;
  var suggestSchedulerStarted = false;
  var suggestWaitStartedAt = 0;

  function isStandalone() {
    try {
      if (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) return true;
      if (window.navigator.standalone === true) return true;
      if (document.referrer && document.referrer.indexOf('android-app://') === 0) return true;
    } catch (e) { /* ignore */ }
    return false;
  }

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function storageGet(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }

  function storageSet(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (e) { /* ignore */ }
  }

  function toast(message, type, opts) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type || 'info', opts || {});
    }
  }

  function platformHint() {
    var ua = navigator.userAgent || '';
    var isAndroid = /Android/i.test(ua);
    var isIOS = /iPhone|iPad|iPod/i.test(ua);
    var isEdge = /Edg\//i.test(ua);
    var isChrome = /Chrome\//i.test(ua) && !isEdge;
    if (isIOS) {
      return 'در Safari از Share و سپس Add to Home Screen استفاده کنید.';
    }
    if (isAndroid) {
      return 'از منوی مرورگر (⋮) گزینه Install app یا Add to Home screen را انتخاب کنید.';
    }
    if (isEdge) {
      return 'در Edge از منوی Apps یا آیکن ⊕ در نوار آدرس برای نصب استفاده کنید.';
    }
    if (isChrome) {
      return 'در Chrome از منوی ⋮ یا آیکن نصب در نوار آدرس استفاده کنید.';
    }
    return 'مرورگر فعلی ممکن است نصب PWA را پشتیبانی نکند. Chrome یا Edge توصیه می‌شود.';
  }

  function isMobile() {
    if (typeof policy.isMobileUa === 'function') {
      return policy.isMobileUa(navigator.userAgent || '');
    }
    return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');
  }

  function isSuggestDismissed() {
    if (typeof policy.isDismissed === 'function') {
      return policy.isDismissed(Date.now(), storageGet);
    }
    return false;
  }

  function isMarkedInstalled() {
    if (typeof policy.isMarkedInstalled === 'function') {
      return policy.isMarkedInstalled(storageGet);
    }
    return storageGet(policy.STORAGE_INSTALLED || 'ws-pwa-installed') === '1';
  }

  function markInstalled() {
    storageSet(policy.STORAGE_INSTALLED || 'ws-pwa-installed', '1');
  }

  function dismissSuggestForDays() {
    var key = policy.STORAGE_DISMISS_UNTIL || 'ws-pwa-suggest-dismiss-until';
    var until = typeof policy.dismissUntilTimestamp === 'function'
      ? policy.dismissUntilTimestamp(Date.now())
      : Date.now() + (7 * 24 * 60 * 60 * 1000);
    storageSet(key, String(until));
  }

  function hasBlockingUi() {
    if (document.body.classList.contains('ws-modal-open')) return true;
    if (document.body.classList.contains('ws-tour-active')) return true;
    if (qs('.ws-modal.is-open')) return true;
    if (qs('.ws-signup-welcome.is-active') || qs('.ws-signup-welcome')) return true;
    if (qs('#wsMobileMoreSheet.is-open')) return true;
    return false;
  }

  function getSuggestModal() {
    return document.getElementById('modal-pwa-install');
  }

  function closeSuggestModal() {
    var modal = getSuggestModal();
    if (!modal) return;
    if (window.WSModal && typeof window.WSModal.close === 'function') {
      window.WSModal.close(modal);
      return;
    }
    modal.classList.remove('is-open');
    document.body.classList.remove('ws-modal-open');
  }

  function openSuggestModal() {
    var modal = getSuggestModal();
    if (!modal || suggestShownThisSession) return false;

    var canShow = typeof policy.shouldAutoSuggest === 'function'
      ? policy.shouldAutoSuggest({
          isStandalone: isStandalone(),
          isMobile: isMobile(),
          hasDeferredPrompt: !!deferredPrompt,
          isMarkedInstalled: isMarkedInstalled(),
          isDismissed: isSuggestDismissed(),
          hasBlockingUi: hasBlockingUi(),
          alreadyShownThisSession: suggestShownThisSession,
        })
      : (!!deferredPrompt && isMobile() && !isStandalone() && !hasBlockingUi());

    if (!canShow) return false;

    suggestShownThisSession = true;
    if (window.WSModal && typeof window.WSModal.open === 'function') {
      window.WSModal.open(modal);
    } else {
      modal.classList.add('is-open');
      document.body.classList.add('ws-modal-open');
    }
    return true;
  }

  function scheduleAutoSuggest() {
    if (suggestSchedulerStarted) return;
    if (isStandalone() || !isMobile() || isMarkedInstalled() || isSuggestDismissed()) return;
    suggestSchedulerStarted = true;
    suggestWaitStartedAt = Date.now();

    var delay = policy.SUGGEST_DELAY_MS || 1800;
    var retry = policy.SUGGEST_RETRY_MS || 2000;
    var maxWait = policy.SUGGEST_MAX_WAIT_MS || 45000;

    function attempt() {
      if (suggestShownThisSession || isStandalone() || isMarkedInstalled() || isSuggestDismissed()) {
        return;
      }
      if (!deferredPrompt) {
        // No beforeinstallprompt yet / unavailable — do not fake system UI; keep waiting briefly.
        if (Date.now() - suggestWaitStartedAt < maxWait) {
          window.setTimeout(attempt, retry);
        }
        return;
      }
      if (hasBlockingUi()) {
        if (Date.now() - suggestWaitStartedAt < maxWait) {
          window.setTimeout(attempt, retry);
        }
        return;
      }
      openSuggestModal();
    }

    var start = function () {
      window.setTimeout(attempt, delay);
    };

    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(function () { start(); }, { timeout: delay + 800 });
    } else {
      start();
    }
  }

  function markDirty() {
    formDirty = true;
  }

  function clearDirty() {
    formDirty = false;
  }

  function trackFormDirtiness() {
    document.addEventListener('input', function (e) {
      var t = e.target;
      if (!t) return;
      if (t.closest && t.closest('form') && (t.matches('input, textarea, select') || t.isContentEditable)) {
        markDirty();
      }
    }, true);
    document.addEventListener('change', function (e) {
      var t = e.target;
      if (t && t.closest && t.closest('form')) markDirty();
    }, true);
    document.addEventListener('submit', function () {
      clearDirty();
    }, true);
  }

  function setInstallUiState(state) {
    var root = qs('[data-ws-pwa-install]');
    if (!root) return;

    var btn = qs('[data-ws-pwa-install-btn]', root);
    var hint = qs('[data-ws-pwa-install-hint]', root);
    var status = qs('[data-ws-pwa-install-status]', root);

    root.hidden = false;
    root.setAttribute('data-state', state);

    if (state === 'standalone') {
      root.hidden = true;
      return;
    }

    if (state === 'installed') {
      if (btn) btn.hidden = true;
      if (status) {
        status.hidden = false;
        status.textContent = 'میزکار روی این دستگاه نصب شده است.';
      }
      if (hint) hint.hidden = true;
      return;
    }

    if (status) status.hidden = true;

    if (state === 'prompt') {
      if (btn) {
        btn.hidden = false;
        btn.disabled = false;
      }
      if (hint) {
        hint.hidden = false;
        hint.textContent = 'با یک کلیک میزکار را مثل اپلیکیشن نصب کنید.';
      }
      return;
    }

    if (btn) btn.hidden = true;
    if (hint) {
      hint.hidden = false;
      hint.textContent = platformHint();
    }
  }

  function refreshInstallUi() {
    if (isStandalone()) {
      document.documentElement.setAttribute('data-ws-display', 'standalone');
      setInstallUiState('standalone');
      return;
    }
    document.documentElement.setAttribute('data-ws-display', 'browser');

    if (isMarkedInstalled()) {
      setInstallUiState('installed');
      return;
    }

    if (deferredPrompt) {
      setInstallUiState('prompt');
      return;
    }

    setInstallUiState('manual');
  }

  async function triggerInstall() {
    if (!deferredPrompt) {
      toast(platformHint(), 'info', { duration: 7000 });
      return;
    }

    var promptEvent = deferredPrompt;
    deferredPrompt = null;

    // Must run inside the user gesture (click) — do not await before prompt().
    promptEvent.prompt();

    closeSuggestModal();

    try {
      var choice = await promptEvent.userChoice;
      if (choice && choice.outcome === 'accepted') {
        markInstalled();
        setInstallUiState('installed');
        toast('میزکار با موفقیت نصب شد.', 'success');
      } else {
        refreshInstallUi();
      }
    } catch (e) {
      toast('نصب انجام نشد. از منوی مرورگر امتحان کنید.', 'warning');
      refreshInstallUi();
    }
  }

  function dismissSuggest() {
    dismissSuggestForDays();
    closeSuggestModal();
  }

  function bindInstallControls() {
    qsa('[data-ws-pwa-install-btn]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        triggerInstall();
      });
    });

    qsa('[data-ws-pwa-suggest-install]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        triggerInstall();
      });
    });

    qsa('[data-ws-pwa-suggest-dismiss]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        dismissSuggest();
      });
    });

    var suggestModal = getSuggestModal();
    if (suggestModal) {
      // Overlay / close = soft dismiss (7 days), same as «فعلاً نه»
      qsa('[data-modal-close]', suggestModal).forEach(function (el) {
        el.addEventListener('click', function () {
          dismissSuggestForDays();
        });
      });
    }
  }

  function showOfflineBanner(online) {
    var el = qs('#wsPwaOfflineBanner');
    if (!el) return;
    if (online) {
      el.hidden = true;
      el.setAttribute('aria-hidden', 'true');
    } else {
      el.hidden = false;
      el.setAttribute('aria-hidden', 'false');
    }
  }

  function bindOnlineStatus() {
    showOfflineBanner(navigator.onLine !== false);
    window.addEventListener('online', function () {
      showOfflineBanner(true);
      toast('اتصال اینترنت برقرار شد.', 'success', { duration: 2500 });
    });
    window.addEventListener('offline', function () {
      showOfflineBanner(false);
    });
  }

  function removeUpdateBanner() {
    if (updateBannerEl && updateBannerEl.parentNode) {
      updateBannerEl.parentNode.removeChild(updateBannerEl);
    }
    updateBannerEl = null;
  }

  function applyWaitingWorker(worker) {
    if (!worker) return;
    worker.postMessage({ type: 'WS_PWA_SKIP_WAITING' });
  }

  function showUpdateBanner(waitingWorker) {
    if (updateBannerEl) return;
    var stack = document.getElementById('mkToastStack') || document.body;
    var el = document.createElement('div');
    el.className = 'ws-pwa-update';
    el.setAttribute('role', 'status');
    el.innerHTML =
      '<div class="ws-pwa-update__body">' +
      '<strong>نسخه جدید میزکار آماده است</strong>' +
      '<span>برای جلوگیری از از دست رفتن اطلاعات فرم، ابتدا ذخیره کنید سپس بروزرسانی کنید.</span>' +
      '</div>' +
      '<div class="ws-pwa-update__actions">' +
      '<button type="button" class="ws-btn ws-btn-ghost ws-btn-sm" data-ws-pwa-update-later>بعداً</button>' +
      '<button type="button" class="ws-btn ws-btn-primary ws-btn-sm" data-ws-pwa-update-now>بروزرسانی</button>' +
      '</div>';
    stack.appendChild(el);
    updateBannerEl = el;

    qs('[data-ws-pwa-update-later]', el).addEventListener('click', function () {
      removeUpdateBanner();
    });
    qs('[data-ws-pwa-update-now]', el).addEventListener('click', function () {
      if (formDirty) {
        var ok = window.confirm('تغییرات ذخیره‌نشده دارید. بروزرسانی صفحه را دوباره بارگذاری می‌کند. ادامه می‌دهید؟');
        if (!ok) return;
      }
      applyWaitingWorker(waitingWorker);
      removeUpdateBanner();
    });
  }

  function watchRegistration(reg) {
    if (!reg) return;
    if (reg.waiting) {
      showUpdateBanner(reg.waiting);
    }
    reg.addEventListener('updatefound', function () {
      var installing = reg.installing;
      if (!installing) return;
      installing.addEventListener('statechange', function () {
        if (installing.state === 'installed' && navigator.serviceWorker.controller) {
          showUpdateBanner(reg.waiting || installing);
        }
      });
    });
  }

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register(SW_URL, { scope: '/workspace/' }).then(function (reg) {
      registration = reg;
      watchRegistration(reg);
      try {
        reg.update();
      } catch (e) { /* ignore */ }
    }).catch(function () {
      // Silent — PWA is progressive enhancement.
    });

    var refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', function () {
      if (refreshing) return;
      if (formDirty) {
        toast('نسخه جدید آماده است. پس از ذخیره، صفحه را تازه‌سازی کنید.', 'update', { duration: 8000 });
        return;
      }
      refreshing = true;
      window.location.reload();
    });
  }

  function init() {
    trackFormDirtiness();
    bindInstallControls();
    bindOnlineStatus();
    refreshInstallUi();

    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredPrompt = e;
      refreshInstallUi();
      scheduleAutoSuggest();
    });

    window.addEventListener('appinstalled', function () {
      deferredPrompt = null;
      markInstalled();
      closeSuggestModal();
      setInstallUiState('installed');
      toast('میزکار فایلینگ دیوار نصب شد.', 'success');
    });

    // If prompt already happened before listeners (rare), still arm scheduler for mobile.
    scheduleAutoSuggest();
    registerServiceWorker();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.wsPwa = {
    install: triggerInstall,
    isStandalone: isStandalone,
    refresh: refreshInstallUi,
    dismissSuggest: dismissSuggest,
    openSuggestModal: openSuggestModal,
  };
})();
