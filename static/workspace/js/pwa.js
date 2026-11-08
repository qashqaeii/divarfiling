/**
 * Workspace PWA client — install prompt, SW lifecycle, offline banner.
 * Non-intrusive: no auto popup on login; install lives in settings.
 */
(function () {
  'use strict';

  var SW_URL = '/workspace/sw.js';
  var STORAGE_DISMISS = 'ws-pwa-install-dismissed';
  var deferredPrompt = null;
  var registration = null;
  var formDirty = false;
  var updateBannerEl = null;

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

  function toast(message, type, opts) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type || 'info', opts || {});
      return;
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

    // manual / unsupported
    if (btn) btn.hidden = true;
    if (hint) {
      hint.hidden = false;
      hint.textContent = platformHint();
    }
  }

  function wasDismissed() {
    try {
      return localStorage.getItem(STORAGE_DISMISS) === '1';
    } catch (e) {
      return false;
    }
  }

  function refreshInstallUi() {
    if (isStandalone()) {
      document.documentElement.setAttribute('data-ws-display', 'standalone');
      setInstallUiState('standalone');
      return;
    }
    document.documentElement.setAttribute('data-ws-display', 'browser');

    if (deferredPrompt) {
      setInstallUiState('prompt');
      return;
    }

    // Heuristic: if related SW controlling and getInstalledRelatedApps available — optional.
    if (navigator.getInstalledRelatedApps) {
      navigator.getInstalledRelatedApps().then(function (apps) {
        if (apps && apps.length) {
          setInstallUiState('installed');
        } else {
          setInstallUiState('manual');
        }
      }).catch(function () {
        setInstallUiState('manual');
      });
      return;
    }

    setInstallUiState('manual');
  }

  async function triggerInstall() {
    if (!deferredPrompt) {
      toast(platformHint(), 'info', { duration: 7000 });
      return;
    }
    deferredPrompt.prompt();
    try {
      var choice = await deferredPrompt.userChoice;
      if (choice && choice.outcome === 'accepted') {
        toast('میزکار با موفقیت نصب شد.', 'success');
        setInstallUiState('installed');
      }
    } catch (e) {
      toast('نصب انجام نشد. از منوی مرورگر امتحان کنید.', 'warning');
    }
    deferredPrompt = null;
    refreshInstallUi();
  }

  function bindInstallControls() {
    qsa('[data-ws-pwa-install-btn]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        triggerInstall();
      });
    });
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
    // Only register on workspace pages (this script is only on workspace base).
    navigator.serviceWorker.register(SW_URL, { scope: '/workspace/' }).then(function (reg) {
      registration = reg;
      watchRegistration(reg);
      // Periodic update check (safe; does not activate automatically).
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
      if (!wasDismissed()) {
        refreshInstallUi();
      } else {
        setInstallUiState('prompt');
      }
    });

    window.addEventListener('appinstalled', function () {
      deferredPrompt = null;
      try { localStorage.setItem(STORAGE_DISMISS, '1'); } catch (e) { /* ignore */ }
      setInstallUiState('installed');
      toast('میزکار فایلینگ دیوار نصب شد.', 'success');
    });

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
    refresh: refreshInstallUi
  };
})();
