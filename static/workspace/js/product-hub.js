(function () {
  'use strict';

  function csrfToken() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function postJson(url) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      credentials: 'same-origin',
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) {
          var err = new Error((data && data.message) || 'error');
          err.data = data;
          err.status = r.status;
          throw err;
        }
        return data;
      });
    });
  }

  function scrollActiveTabIntoView() {
    var active = document.querySelector('[data-ph-tabs] .ph-tab.is-active');
    if (!active || typeof active.scrollIntoView !== 'function') return;
    try {
      active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
    } catch (e) {
      active.scrollIntoView(false);
    }
  }

  function initStickyTabsOffset() {
    var wrap = document.querySelector('.ph-tabs-wrap');
    if (!wrap) return;
    var h = wrap.offsetHeight;
    document.documentElement.style.setProperty('--ph-tabs-h', h + 'px');
  }

  function openModal(id) {
    if (window.WSModal && typeof window.WSModal.open === 'function') {
      window.WSModal.open(id);
      return;
    }
    var modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('is-open');
    document.body.classList.add('ws-modal-open');
  }

  function composeModalForTab(tab) {
    if (tab === 'bugs') return 'modal-ph-bug';
    if (tab === 'features') return 'modal-ph-feat-filter';
    return 'modal-ph-request';
  }

  function fabLabelForTab(tab) {
    if (tab === 'bugs') return 'گزارش مشکل';
    if (tab === 'features') return 'فیلتر';
    if (tab === 'requests' || tab === 'my' || tab === 'overview' || tab === 'roadmap') return 'پیشنهاد جدید';
    return 'ثبت جدید';
  }

  function syncFab() {
    var hub = document.querySelector('[data-ph-hub]');
    var fab = document.getElementById('phFab');
    if (!hub || !fab) return;
    var tab = hub.getAttribute('data-ph-tab') || 'overview';
    var licensed = !!document.getElementById('modal-ph-request');
    var show = false;
    var label = fabLabelForTab(tab);
    var modalId = composeModalForTab(tab);

    if (tab === 'features') {
      show = true;
      fab.setAttribute('data-modal-target', 'modal-ph-feat-filter');
    } else if (licensed && (tab === 'requests' || tab === 'bugs' || tab === 'my' || tab === 'overview' || tab === 'roadmap')) {
      show = true;
      fab.setAttribute('data-modal-target', modalId);
    } else if (licensed && tab === 'changelog') {
      show = false;
    }

    fab.classList.toggle('is-visible', show);
    var labelEl = fab.querySelector('[data-ph-fab-label]');
    if (labelEl) labelEl.textContent = label;
    fab.setAttribute('aria-label', label);

    if (tab === 'bugs') {
      fab.querySelector('i') && (fab.querySelector('i').className = 'fas fa-bug');
    } else if (tab === 'features') {
      fab.querySelector('i') && (fab.querySelector('i').className = 'fas fa-sliders');
    } else {
      fab.querySelector('i') && (fab.querySelector('i').className = 'fas fa-plus');
    }
  }

  function bindComposeOpeners() {
    document.querySelectorAll('[data-ph-compose-open]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var hub = document.querySelector('[data-ph-hub]');
        var tab = hub ? hub.getAttribute('data-ph-tab') : 'requests';
        openModal(composeModalForTab(tab === 'features' ? 'requests' : tab));
      });
    });

    var fab = document.getElementById('phFab');
    if (fab) {
      fab.addEventListener('click', function () {
        var target = fab.getAttribute('data-modal-target') || 'modal-ph-request';
        openModal(target);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    scrollActiveTabIntoView();
    initStickyTabsOffset();
    syncFab();
    bindComposeOpeners();
    window.addEventListener('resize', initStickyTabsOffset);

    var params = new URLSearchParams(window.location.search);
    var openId = params.get('open') || document.body.dataset.openModal;
    if (openId && (openId === 'modal-ph-request' || openId === 'modal-ph-bug' || openId === 'modal-ph-feat-filter')) {
      openModal(openId);
    }
  });

  document.addEventListener('click', function (ev) {
    var voteBtn = ev.target.closest('[data-ph-vote]');
    if (voteBtn) {
      ev.preventDefault();
      if (voteBtn.disabled) return;
      var url = voteBtn.getAttribute('data-ph-vote');
      voteBtn.disabled = true;
      postJson(url).then(function (data) {
        voteBtn.classList.toggle('is-on', !!data.voted);
        voteBtn.setAttribute('aria-pressed', data.voted ? 'true' : 'false');
        var countEl = voteBtn.querySelector('[data-ph-count]');
        if (countEl) countEl.textContent = data.votes_count;
        if (typeof showToast === 'function') {
          showToast(data.voted ? 'رای شما ثبت شد' : 'رای برداشته شد', 'success');
        }
      }).catch(function (err) {
        if (err.data && err.data.upgrade_url) {
          window.location.href = err.data.upgrade_url;
          return;
        }
        if (typeof showToast === 'function') {
          showToast((err.data && err.data.message) || 'خطا در ثبت رای', 'error');
        }
      }).finally(function () {
        voteBtn.disabled = false;
      });
      return;
    }

    var followBtn = ev.target.closest('[data-ph-follow]');
    if (followBtn) {
      ev.preventDefault();
      if (followBtn.disabled) return;
      var furl = followBtn.getAttribute('data-ph-follow');
      followBtn.disabled = true;
      postJson(furl).then(function (data) {
        followBtn.classList.toggle('is-on', !!data.following);
        followBtn.textContent = data.following ? 'در حال دنبال' : 'دنبال کردن';
        var wrap = followBtn.parentElement;
        var fc = wrap && wrap.querySelector('[data-ph-follows]');
        if (fc) fc.textContent = data.follows_count;
        if (typeof showToast === 'function') {
          showToast(data.following ? 'اکنون این پیشنهاد را دنبال می‌کنید' : 'دنبال کردن لغو شد', 'info');
        }
      }).catch(function (err) {
        if (err.data && err.data.upgrade_url) {
          window.location.href = err.data.upgrade_url;
          return;
        }
        if (typeof showToast === 'function') {
          showToast((err.data && err.data.message) || 'خطا', 'error');
        }
      }).finally(function () {
        followBtn.disabled = false;
      });
    }
  });
})();
