(function () {
  'use strict';

  function csrfToken() {
    var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return el ? el.value : '';
  }

  var DIVAR_OTP_TTL_SECONDS = 120;

  function toFaDigits(str) {
    var fa = '۰۱۲۳۴۵۶۷۸۹';
    return String(str).replace(/\d/g, function (d) {
      return fa[Number(d)];
    });
  }

  function bindDivarOtpTimer(modal) {
    if (!modal) return null;
    if (modal._divarOtpTimerApi) return modal._divarOtpTimerApi;

    var intervalId = null;

    function queryTimerEls() {
      return {
        wrap: modal.querySelector('[data-divar-otp-timer]'),
        text: modal.querySelector('[data-divar-otp-timer-text]'),
        expired: modal.querySelector('[data-divar-otp-expired]'),
        resend: modal.querySelector('[data-divar-otp-resend]'),
        verify: modal.querySelector('[data-divar-verify-otp]'),
        otpInput: modal.querySelector('[data-divar-otp]'),
      };
    }

    function clear() {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
      var e = queryTimerEls();
      if (e.wrap) {
        e.wrap.hidden = true;
        e.wrap.classList.remove('is-warning', 'is-expired');
      }
      if (e.expired) e.expired.hidden = true;
      if (e.resend) e.resend.hidden = true;
      modal.dataset.divarOtpExpired = '0';
    }

    function start(seconds) {
      clear();
      var total = Number(seconds) || DIVAR_OTP_TTL_SECONDS;
      var deadline = Date.now() + total * 1000;
      var e = queryTimerEls();
      if (e.wrap) e.wrap.hidden = false;
      modal.dataset.divarOtpExpired = '0';

      function tick() {
        var left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        var mins = Math.floor(left / 60);
        var secs = left % 60;
        var clock =
          (mins < 10 ? '0' : '') + mins + ':' + (secs < 10 ? '0' : '') + secs;
        if (e.text) e.text.textContent = toFaDigits(clock);
        if (e.wrap) {
          e.wrap.classList.toggle('is-warning', left > 0 && left <= 30);
          e.wrap.classList.toggle('is-expired', left === 0);
        }
        var expired = left === 0;
        modal.dataset.divarOtpExpired = expired ? '1' : '0';
        if (e.verify && !e.verify.classList.contains('is-loading')) {
          e.verify.disabled = expired;
        }
        if (expired) {
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }
          if (e.expired) e.expired.hidden = false;
          if (e.resend) e.resend.hidden = false;
        }
      }

      tick();
      intervalId = setInterval(tick, 1000);
      if (e.otpInput) {
        try {
          e.otpInput.focus();
        } catch (ignoreErr) {
          /* noop */
        }
      }
    }

    modal._divarOtpTimerApi = { clear: clear, start: start };
    return modal._divarOtpTimerApi;
  }

  function setModalSubmitBusy(button, busy, loadingLabel) {
    if (!button) return;
    if (!button.dataset.idleLabel) {
      button.dataset.idleLabel = (button.textContent || '').trim();
    }
    var idle = button.dataset.idleLabel;
    button.disabled = !!busy;
    button.classList.toggle('is-loading', !!busy);
    button.setAttribute('aria-busy', busy ? 'true' : 'false');
    if (busy) {
      button.innerHTML =
        '<i class="fas fa-spinner fa-spin ws-divar-modal-btn__ico" aria-hidden="true"></i>' +
        '<span>' + (loadingLabel || 'لطفاً صبر کنید…') + '</span>';
    } else {
      button.textContent = idle;
    }
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

  var ACTION_LABELS = {
    connect: 'اتصال به دیوار',
    fetch: 'دریافت از دیوار',
    captcha: 'حل کپچا',
    reconnect: 'اتصال مجدد',
    loading: 'در حال دریافت...',
  };

  var ACTION_ICONS = {
    connect: 'fa-link',
    reconnect: 'fa-rotate-right',
    fetch: 'fa-cloud-arrow-down',
    captcha: 'fa-shield-halved',
    loading: 'fa-spinner fa-spin',
  };

  function initBox(root) {
    if (!root || root.dataset.divarInit === '1') return;
    root.dataset.divarInit = '1';

    var btn = root.querySelector('[data-divar-action]');
    var statusEl = root.querySelector('[data-divar-status]');
    var maskedPhoneEl = root.querySelector('[data-divar-masked-phone]');
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
    var otpTimer = modal ? bindDivarOtpTimer(modal) : null;

    function setError(msg) {
      if (!errEl) return;
      errEl.textContent = msg || '';
      errEl.hidden = !msg;
    }

    function setButtonState(state, label) {
      if (!btn) return;
      var resolved = state || 'connect';
      btn.dataset.state = resolved;
      var labelEl = btn.querySelector('[data-divar-action-label]');
      var iconEl = btn.querySelector('[data-divar-action-icon]');
      var text = label || ACTION_LABELS[resolved] || ACTION_LABELS.connect;
      if (labelEl) labelEl.textContent = text;
      else btn.textContent = text;
      if (iconEl) {
        iconEl.className = 'fas mk-owner-divar-fetch__icon ' + (ACTION_ICONS[resolved] || ACTION_ICONS.connect);
      }
      btn.disabled = resolved === 'loading';
      btn.classList.toggle('is-loading', resolved === 'loading');
      btn.classList.toggle('is-captcha', resolved === 'captcha');
      btn.classList.toggle('is-reconnect', resolved === 'reconnect');
      btn.setAttribute('aria-busy', resolved === 'loading' ? 'true' : 'false');
    }

    function sessionConnected(st) {
      if (!st) return false;
      if (st.has_session) return true;
      if (st.divar_phone_masked) return true;
      var bs = st.button_state || '';
      return bs === 'fetch' || bs === 'captcha';
    }

    function updateConnectionBadge(st) {
      if (!statusEl) return;
      var show = sessionConnected(st);
      statusEl.hidden = !show;
      if (!show) {
        var details = statusEl.querySelector('.mk-owner-divar-status__details');
        if (details) details.removeAttribute('open');
        return;
      }
      if (maskedPhoneEl && st && st.divar_phone_masked) {
        maskedPhoneEl.textContent = st.divar_phone_masked;
      }
    }

    function applyStatus(st) {
      if (!st) return;
      setButtonState(st.button_state || 'connect', ACTION_LABELS[st.button_state] || null);
      updateConnectionBadge(st);
      syncCaptchaUrl(st);
    }

    function syncCaptchaUrl(st) {
      var fromStatus = (st && st.captcha_post_url) || root.dataset.captchaPostUrl || '';
      var fallback = root.dataset.captchaFallbackUrl || '';
      if (fromStatus) root.dataset.captchaPostUrl = fromStatus;
      else if (!root.dataset.captchaPostUrl && fallback) root.dataset.captchaPostUrl = fallback;
    }

    applyStatus({
      button_state: root.dataset.initialState || 'connect',
      has_session: root.dataset.initialHasSession === '1',
      divar_phone_masked: root.dataset.initialMaskedPhone || '',
    });
    if ((root.dataset.initialState || '') === 'captcha') {
      syncCaptchaUrl({ captcha_post_url: root.dataset.captchaPostUrl });
    }

    function defaultDivarPhone() {
      if (!phoneInput) return '';
      return phoneInput.getAttribute('data-divar-default-phone') || '';
    }

    function openModal() {
      if (!modal) return;
      setError('');
      pendingPhone = '';
      if (phoneStep) phoneStep.hidden = false;
      if (otpStep) otpStep.hidden = true;
      if (phoneInput) phoneInput.value = defaultDivarPhone();
      if (otpInput) otpInput.value = '';
      var sendBtnReset = modal.querySelector('[data-divar-send-otp]');
      var verifyBtnReset = modal.querySelector('[data-divar-verify-otp]');
      setModalSubmitBusy(sendBtnReset, false);
      setModalSubmitBusy(verifyBtnReset, false);
      if (otpTimer) otpTimer.clear();
      if (window.WSModal && typeof window.WSModal.open === 'function') {
        window.WSModal.open(modal.id || 'divar-connect-modal');
      } else {
        modal.removeAttribute('hidden');
        modal.classList.add('is-open');
        document.body.classList.add('ws-modal-open');
      }
    }

    function closeModal() {
      if (!modal) return;
      if (window.WSModal && typeof window.WSModal.close === 'function') {
        window.WSModal.close(modal);
      } else {
        modal.classList.remove('is-open');
        if (modal.hasAttribute('data-modal-uses-hidden')) {
          modal.setAttribute('hidden', '');
        }
        document.body.classList.remove('ws-modal-open');
      }
    }

    if (modal && modal.dataset.divarOtpHandlersBound !== '1') {
      modal.dataset.divarOtpHandlersBound = '1';
      var sendBtn = modal.querySelector('[data-divar-send-otp]');
      if (sendBtn) {
        sendBtn.addEventListener('click', function () {
          if (sendBtn.disabled) return;
          setError('');
          setModalSubmitBusy(sendBtn, true, 'در حال ارسال…');
          postJson(sendUrl, { phone: phoneInput ? phoneInput.value : '' }).then(function (res) {
            setModalSubmitBusy(sendBtn, false);
            if (!res.data.ok) {
              setError(res.data.error || 'ارسال کد ناموفق بود');
              return;
            }
            pendingPhone = res.data.phone || (phoneInput ? phoneInput.value : '');
            if (phoneStep) phoneStep.hidden = true;
            if (otpStep) otpStep.hidden = false;
            if (otpTimer) {
              otpTimer.start(res.data.otp_ttl_seconds || DIVAR_OTP_TTL_SECONDS);
            }
          }).catch(function () {
            setModalSubmitBusy(sendBtn, false);
            setError('خطا در ارتباط با سرور. دوباره تلاش کنید.');
          });
        });
      }
      var resendBtn = modal.querySelector('[data-divar-otp-resend]');
      if (resendBtn) {
        resendBtn.addEventListener('click', function () {
          if (otpTimer) otpTimer.clear();
          setError('');
          if (phoneStep) phoneStep.hidden = false;
          if (otpStep) otpStep.hidden = true;
          if (otpInput) otpInput.value = '';
          var verifyBtnReset = modal.querySelector('[data-divar-verify-otp]');
          setModalSubmitBusy(verifyBtnReset, false);
        });
      }
      var verifyBtn = modal.querySelector('[data-divar-verify-otp]');
      if (verifyBtn) {
        verifyBtn.addEventListener('click', function () {
          if (verifyBtn.disabled) return;
          if (modal.dataset.divarOtpExpired === '1') {
            setError('مهلت ورود کد تمام شده. «ارسال مجدد کد» را بزنید.');
            return;
          }
          setError('');
          setModalSubmitBusy(verifyBtn, true, 'در حال تأیید…');
          postJson(verifyUrl, {
            phone: pendingPhone,
            otp: otpInput ? otpInput.value : '',
          }).then(function (res) {
            setModalSubmitBusy(verifyBtn, false);
            if (!res.data.ok) {
              setError(res.data.error || 'تأیید ناموفق بود');
              return;
            }
            closeModal();
            applyStatus(res.data.status);
          }).catch(function () {
            setModalSubmitBusy(verifyBtn, false);
            setError('خطا در ارتباط با سرور. دوباره تلاش کنید.');
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
        if (!root.dataset.captchaPostUrl && root.dataset.captchaFallbackUrl) {
          root.dataset.captchaPostUrl = root.dataset.captchaFallbackUrl;
        }
        setButtonState('captcha', 'بررسی مجدد');
        return;
      }
      if (state === 'fetch' && fetchUrl) {
        setButtonState('loading');
        postJson(fetchUrl, {}).then(function (res) {
          var data = res.data || {};
          if (data.code === 'captcha_required') {
            root.dataset.captchaPostUrl = data.post_url || '';
            applyStatus(data.status || { button_state: 'captcha', has_session: true });
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
          applyStatus(data.status || { button_state: 'fetch', has_session: true });
        }).catch(function () {
          setButtonState('fetch');
        });
      }
    });

    var disconnectBtn = root.querySelector('[data-divar-disconnect]');
    if (disconnectBtn && disconnectUrl) {
      disconnectBtn.addEventListener('click', function () {
        postJson(disconnectUrl, {}).then(function (res) {
          var data = (res && res.data) || {};
          applyStatus(data.status || { button_state: 'connect', has_session: false });
        });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-divar-contact-box]').forEach(initBox);
  });
})();
