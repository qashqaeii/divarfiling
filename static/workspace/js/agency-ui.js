/**
 * Agency Hub UI — frontend polish only (no backend logic)
 */
(function () {
  'use strict';

  var IR_MOBILE = /^09\d{9}$/;

  function normalizePhone(raw) {
    var p = (raw || '').trim().replace(/[\s\-()]/g, '');
    if (p.indexOf('+98') === 0) p = '0' + p.slice(3);
    if (p.indexOf('98') === 0 && p.length === 12) p = '0' + p.slice(2);
    return p;
  }

  function parsePhones(text) {
    return (text || '')
      .split(/[\n,;]+/)
      .map(normalizePhone)
      .filter(Boolean);
  }

  function initInvitePhonePreview() {
    var textarea = document.getElementById('invitePhones');
    var preview = document.getElementById('agencyPhonePreview');
    var list = document.getElementById('agencyPhoneList');
    var countEl = document.getElementById('agencyPhoneCount');
    var errorsEl = document.getElementById('agencyPhoneErrors');
    var submitBtn = document.getElementById('agencyInviteSubmit');
    if (!textarea || !preview || !list) return;

    function render() {
      var phones = parsePhones(textarea.value);
      var unique = [];
      var seen = {};
      var invalid = [];

      phones.forEach(function (p) {
        if (seen[p]) return;
        seen[p] = true;
        if (IR_MOBILE.test(p)) unique.push(p);
        else invalid.push(p);
      });

      list.innerHTML = '';
      unique.forEach(function (p) {
        var li = document.createElement('li');
        li.className = 'agency-phone-chip agency-phone-chip--ok';
        li.textContent = p;
        list.appendChild(li);
      });
      invalid.forEach(function (p) {
        var li = document.createElement('li');
        li.className = 'agency-phone-chip agency-phone-chip--bad';
        li.textContent = p;
        li.title = 'فرمت نامعتبر — باید ۱۱ رقم و با ۰۹ شروع شود';
        list.appendChild(li);
      });

      var total = unique.length + invalid.length;
      preview.hidden = total === 0;
      if (countEl) countEl.textContent = String(unique.length);

      if (errorsEl) {
        if (invalid.length) {
          errorsEl.hidden = false;
          errorsEl.textContent = invalid.length + ' شماره نامعتبر — قبل از ارسال اصلاح کنید.';
        } else {
          errorsEl.hidden = true;
          errorsEl.textContent = '';
        }
      }

      if (submitBtn) {
        submitBtn.disabled = total > 0 && unique.length === 0;
      }
    }

    textarea.addEventListener('input', render);
    textarea.addEventListener('blur', render);
    render();
  }

  function initModalInvitePreview() {
    var input = document.getElementById('agencyInvitePhone');
    var hint = document.getElementById('agencyModalPhoneHint');
    if (!input) return;

    function check() {
      var p = normalizePhone(input.value);
      if (!p) {
        if (hint) { hint.hidden = true; hint.textContent = ''; }
        return;
      }
      if (hint) {
        hint.hidden = false;
        hint.className = 'agency-form-helper' + (IR_MOBILE.test(p) ? ' agency-form-helper--ok' : ' agency-form-helper--bad');
        hint.textContent = IR_MOBILE.test(p) ? 'شماره معتبر است' : 'شماره باید ۱۱ رقم و با ۰۹ شروع شود';
      }
    }

    input.addEventListener('input', check);
    input.addEventListener('blur', check);
  }

  function initStickyStepFooter() {
    var footer = document.querySelector('.agency-step-footer--sticky');
    if (!footer || window.matchMedia('(min-width: 769px)').matches) return;
    document.body.classList.add('agency-has-sticky-footer');
  }

  function initNavScrollHint() {
    document.querySelectorAll('.agency-hub-nav__track, .a360-tabs').forEach(function (track) {
      function update() {
        var atEnd = track.scrollWidth - track.clientWidth - track.scrollLeft < 8;
        var atStart = track.scrollLeft < 8;
        track.classList.toggle('is-scroll-end', atEnd);
        track.classList.toggle('is-scroll-start', atStart);
      }
      track.addEventListener('scroll', update, { passive: true });
      update();
    });
  }

  function initMemberFilterEmpty() {
    var search = document.getElementById('agencyMemberSearch');
    if (!search) return;

    function checkEmpty() {
      var rows = document.querySelectorAll('#agencyMembersTable tbody tr[data-name], .agency-member-card[data-name]');
      var visible = 0;
      rows.forEach(function (el) {
        if (el.style.display !== 'none') visible++;
      });
      var empty = document.getElementById('agencyMembersFilterEmpty');
      if (empty) empty.hidden = visible > 0;
    }

    search.addEventListener('input', checkEmpty);
    var statusF = document.getElementById('agencyMemberStatusFilter');
    var licenseF = document.getElementById('agencyMemberLicenseFilter');
    if (statusF) statusF.addEventListener('change', checkEmpty);
    if (licenseF) licenseF.addEventListener('change', checkEmpty);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initInvitePhonePreview();
    initModalInvitePreview();
    initStickyStepFooter();
    initNavScrollHint();
    initMemberFilterEmpty();
  });
})();
