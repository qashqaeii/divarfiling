(function () {
  'use strict';

  function csrfToken() {
    var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return el ? el.value : '';
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  function initBox(root) {
    if (!root || root.dataset.divarInit === '1') return;
    root.dataset.divarInit = '1';

    var btn = root.querySelector('[data-divar-action]');
    var modal = document.getElementById(root.dataset.divarModalId || 'divar-connect-modal');
    var phoneInput = modal ? modal.querySelector('[data-divar-phone]') : null;
    var otpInput = modal ? modal.querySelector('[data-divar-otp]') : null;
    var otpStep = modal ? modal.querySelector('[data-divar-step="otp"]') : null;
    var phoneStep = modal ? modal.querySelector('[data-divar-step="phone"]') : null;
    var errEl = modal ? modal.querySelector('[data-divar-error]') : null;
    var sendUrl = root.dataset.sendOtpUrl;
    var verifyUrl = root.dataset.verifyOtpUrl;
    var fetchUrl = root.dataset.fetchUrl;
    var disconnectUrl = root.dataset.disconnectUrl;
    var ownerPhone = document.getElementById(root.dataset.ownerPhoneId || '');
    var ownerName = document.getElementById(root.dataset.ownerNameId || '');
    var pendingPhone = '';

    function setError(msg) {
      if (!errEl) return;
      errEl.textContent = msg || '';
      errEl.hidden = !msg;
    }

    function setButtonState(state, label) {
      if (!btn) return;
      btn.dataset.state = state;
      if (label) btn.textContent = label;
      btn.disabled = state === 'loading';
    }

    function applyStatus(st) {
      if (!st) return;
      var map = {
        connect: 'اتصال به دیوار',
        fetch: 'دریافت از دیوار',
        captcha: 'حل کپچا',
        reconnect: 'اتصال مجدد',
        loading: 'در حال دریافت...',
      };
      setButtonState(st.button_state || 'connect', map[st.button_state] || map.connect);
    }

    applyStatus({
      button_state: root.dataset.initialState || 'connect',
    });

    function openModal() {
      if (!modal) return;
      setError('');
      pendingPhone = '';
      if (phoneStep) phoneStep.hidden = false;
      if (otpStep) otpStep.hidden = true;
      if (phoneInput) phoneInput.value = '';
      if (otpInput) otpInput.value = '';
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
    }

    function closeModal() {
      if (!modal) return;
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
    }

    if (modal) {
      modal.querySelectorAll('[data-divar-close]').forEach(function (el) {
        el.addEventListener('click', closeModal);
      });
      var sendBtn = modal.querySelector('[data-divar-send-otp]');
      if (sendBtn) {
        sendBtn.addEventListener('click', function () {
          setError('');
          postJson(sendUrl, { phone: phoneInput ? phoneInput.value : '' }).then(function (res) {
            if (!res.data.ok) {
              setError(res.data.error || 'ارسال کد ناموفق بود');
              return;
            }
            pendingPhone = res.data.phone || (phoneInput ? phoneInput.value : '');
            if (phoneStep) phoneStep.hidden = true;
            if (otpStep) otpStep.hidden = false;
          });
        });
      }
      var verifyBtn = modal.querySelector('[data-divar-verify-otp]');
      if (verifyBtn) {
        verifyBtn.addEventListener('click', function () {
          setError('');
          postJson(verifyUrl, {
            phone: pendingPhone,
            otp: otpInput ? otpInput.value : '',
          }).then(function (res) {
            if (!res.data.ok) {
              setError(res.data.error || 'تأیید ناموفق بود');
              return;
            }
            closeModal();
            applyStatus(res.data.status);
          });
        });
      }
    }

    if (!btn) return;

    btn.addEventListener('click', function () {
      var state = btn.dataset.state || 'connect';
      if (state === 'connect' || state === 'reconnect') {
        openModal();
        return;
      }
      if (state === 'captcha') {
        var postUrl = root.dataset.captchaPostUrl;
        if (postUrl) window.open(postUrl, '_blank', 'noopener');
        setButtonState('fetch', 'بررسی مجدد');
        return;
      }
      if (state === 'fetch' && fetchUrl) {
        setButtonState('loading', 'در حال دریافت...');
        postJson(fetchUrl, {}).then(function (res) {
          var data = res.data || {};
          if (data.code === 'captcha_required') {
            root.dataset.captchaPostUrl = data.post_url || '';
            setButtonState('captcha', 'حل کپچا');
            return;
          }
          if (!data.ok) {
            setError(data.error || 'دریافت ناموفق بود');
            applyStatus(data.status || { button_state: 'reconnect' });
            return;
          }
          if (ownerPhone && data.phone) ownerPhone.value = data.phone;
          if (ownerName && data.owner_name_hint && !ownerName.value) {
            ownerName.value = data.owner_name_hint;
          }
          applyStatus(data.status || { button_state: 'fetch' });
        }).catch(function () {
          setButtonState('fetch', 'دریافت از دیوار');
        });
      }
    });

    var disconnectBtn = root.querySelector('[data-divar-disconnect]');
    if (disconnectBtn && disconnectUrl) {
      disconnectBtn.addEventListener('click', function () {
        postJson(disconnectUrl, {}).then(function () {
          applyStatus({ button_state: 'connect' });
        });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-divar-contact-box]').forEach(initBox);
  });
})();
