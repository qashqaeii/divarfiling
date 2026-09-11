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

  function initInvitePhoneTags() {
    var form = document.getElementById('agencyInviteForm');
    var input = document.getElementById('invitePhoneInput');
    var addBtn = document.getElementById('invitePhoneAdd');
    var tagList = document.getElementById('agencyTagList');
    var hidden = document.getElementById('invitePhonesHidden');
    var errorEl = document.getElementById('agencyTagInputError');
    var submitBtn = document.getElementById('agencyInviteSubmit');
    var clearBtn = document.getElementById('agencyInviteClear');
    var counterUsed = document.getElementById('agencyInviteCounterUsed');
    var counterTotal = document.getElementById('agencyInviteCounterTotal');
    var counterRemain = document.getElementById('agencyInviteCounterRemain');
    if (!form || !input || !tagList || !hidden) return;

    var maxCapacity = parseInt(form.getAttribute('data-invite-capacity') || '0', 10);
    if (isNaN(maxCapacity) || maxCapacity < 0) maxCapacity = 0;
    var tags = [];

    function showError(msg) {
      if (!errorEl) return;
      if (msg) {
        errorEl.hidden = false;
        errorEl.textContent = msg;
      } else {
        errorEl.hidden = true;
        errorEl.textContent = '';
      }
    }

    function syncHidden() {
      hidden.value = tags.join('\n');
    }

    function updateUI() {
      if (counterUsed) counterUsed.textContent = String(tags.length);
      if (counterTotal) counterTotal.textContent = String(maxCapacity);
      var remain = Math.max(0, maxCapacity - tags.length);
      if (counterRemain) {
        counterRemain.textContent = remain > 0
          ? remain + ' ظرفیت باقی‌مانده'
          : 'ظرفیت تکمیل شده';
      }
      var atLimit = tags.length >= maxCapacity;
      input.disabled = atLimit || maxCapacity === 0;
      if (addBtn) addBtn.disabled = atLimit || maxCapacity === 0;
      if (submitBtn) submitBtn.disabled = tags.length === 0;
      if (clearBtn) clearBtn.disabled = tags.length === 0;
      syncHidden();
    }

    function renderTags() {
      tagList.innerHTML = '';
      tags.forEach(function (phone, index) {
        var chip = document.createElement('span');
        chip.className = 'agency-phone-tag';
        chip.textContent = phone;

        var remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'agency-phone-tag__remove';
        remove.setAttribute('aria-label', 'حذف ' + phone);
        remove.innerHTML = '&times;';
        remove.addEventListener('click', function () {
          tags.splice(index, 1);
          renderTags();
          updateUI();
          showError('');
        });

        chip.appendChild(remove);
        tagList.appendChild(chip);
      });
      updateUI();
    }

    function tryAddPhone(raw) {
      showError('');
      var phone = normalizePhone(raw);
      if (!phone) return false;
      if (!IR_MOBILE.test(phone)) {
        showError('شماره موبایل معتبر نیست.');
        return false;
      }
      if (tags.indexOf(phone) !== -1) {
        showError('این شماره قبلاً اضافه شده است.');
        return false;
      }
      if (tags.length >= maxCapacity) {
        showError('ظرفیت تکمیل شده است.');
        return false;
      }
      tags.push(phone);
      input.value = '';
      renderTags();
      input.focus();
      return true;
    }

    function onAddClick() {
      tryAddPhone(input.value);
    }

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        tryAddPhone(input.value);
      } else if (e.key === ',') {
        e.preventDefault();
        tryAddPhone(input.value);
      }
    });

    if (addBtn) addBtn.addEventListener('click', onAddClick);

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        tags = [];
        renderTags();
        showError('');
        input.focus();
      });
    }

    form.addEventListener('submit', function (e) {
      if (tags.length === 0) {
        e.preventDefault();
        showError('حداقل یک شماره معتبر اضافه کنید.');
        return;
      }
      syncHidden();
    });

    renderTags();
  }

  function initInvitePhonePreview() {
    initInvitePhoneTags();
  }

  function initAgencyInviteModal() {
    var modal = document.getElementById('agencyInviteModal');
    if (!modal) return;

    var phoneInput = document.getElementById('agencyInvitePhone');
    var bodyLockClass = 'agency-modal-open';

    function openModal() {
      modal.classList.add('show');
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add(bodyLockClass);
      if (phoneInput) {
        window.setTimeout(function () {
          phoneInput.focus();
        }, 50);
      }
    }

    function closeModal() {
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove(bodyLockClass);
    }

    document.querySelectorAll('[data-bs-target="#agencyInviteModal"]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        openModal();
      });
    });

    modal.querySelectorAll('[data-bs-dismiss="modal"]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        closeModal();
      });
    });

    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('show')) closeModal();
    });
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
    var footers = document.querySelectorAll('.agency-onboard-footer--sticky');
    if (!footers.length || window.matchMedia('(min-width: 769px)').matches) return;
    document.body.classList.add('agency-has-sticky-footer');
  }

  function initNavScrollHint() {
    document.querySelectorAll('.agency-hub-nav__track, .a360-tabs, .amh-tabs').forEach(function (track) {
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

  function guardMemberSearchInput(input) {
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('autocorrect', 'off');
    input.setAttribute('spellcheck', 'false');
    input.setAttribute('data-lpignore', 'true');
    input.setAttribute('data-1p-ignore', 'true');
    input.setAttribute('data-form-type', 'other');
    if (!input.getAttribute('role')) input.setAttribute('role', 'searchbox');
    input.setAttribute('readonly', 'readonly');
    input.addEventListener('focus', function () {
      input.removeAttribute('readonly');
    }, { once: true });
  }

  function clearPhoneAutofill(input) {
    var value = (input.value || '').trim();
    if (!value || !IR_MOBILE.test(normalizePhone(value))) return false;
    input.value = '';
    return true;
  }

  function initMemberFilters() {
    var search = document.getElementById('agencyMemberSearch');
    var statusF = document.getElementById('agencyMemberStatusFilter');
    var licenseF = document.getElementById('agencyMemberLicenseFilter');
    var clearBtn = document.getElementById('agencyMemberFilterClear');
    var empty = document.getElementById('agencyMembersFilterEmpty');
    if (!search) return;

    guardMemberSearchInput(search);

    var userEdited = false;

    function hasActiveFilters() {
      return !!(search.value.trim() || (statusF && statusF.value) || (licenseF && licenseF.value));
    }

    function updateClearBtn() {
      if (clearBtn) clearBtn.hidden = !hasActiveFilters();
    }

    function checkEmpty() {
      var rows = document.querySelectorAll('#agencyMembersTable tbody tr[data-name], .agency-member-card[data-name]');
      var visible = 0;
      rows.forEach(function (el) {
        if (el.style.display !== 'none') visible++;
      });
      if (empty) empty.hidden = visible > 0 || !hasActiveFilters();
    }

    function filterMembers() {
      var q = (search.value || '').trim().toLowerCase();
      var st = statusF ? statusF.value : '';
      var lic = licenseF ? licenseF.value : '';
      document.querySelectorAll('#agencyMembersTable tbody tr[data-name], .agency-member-card[data-name]').forEach(function (el) {
        var name = el.getAttribute('data-name') || '';
        var phone = el.getAttribute('data-phone') || '';
        var matchQ = !q || name.indexOf(q) !== -1 || phone.indexOf(q) !== -1;
        var matchS = !st || el.getAttribute('data-status') === st;
        var matchL = !lic || el.getAttribute('data-license') === lic;
        el.style.display = matchQ && matchS && matchL ? '' : 'none';
      });
      updateClearBtn();
      checkEmpty();
    }

    function resetFilters() {
      userEdited = false;
      search.value = '';
      if (statusF) statusF.value = '';
      if (licenseF) licenseF.value = '';
      filterMembers();
      search.focus();
    }

    function sweepAutofill() {
      if (userEdited) return;
      if (clearPhoneAutofill(search) || search.value.trim()) {
        search.value = '';
        filterMembers();
      }
    }

    search.addEventListener('input', function () {
      userEdited = true;
      filterMembers();
    });
    if (statusF) statusF.addEventListener('change', filterMembers);
    if (licenseF) licenseF.addEventListener('change', filterMembers);
    if (clearBtn) clearBtn.addEventListener('click', resetFilters);

    search.value = '';
    filterMembers();
    requestAnimationFrame(function () {
      requestAnimationFrame(sweepAutofill);
    });
    window.setTimeout(sweepAutofill, 120);
    window.setTimeout(sweepAutofill, 500);
    window.setTimeout(sweepAutofill, 1000);
  }

  function initAdvisor360Search() {
    document.querySelectorAll('.a360-search-input').forEach(function (input) {
      guardMemberSearchInput(input);
      var userEdited = !!input.value.trim();
      input.addEventListener('input', function () { userEdited = true; });
      function sweep() {
        if (userEdited) return;
        if (clearPhoneAutofill(input)) input.value = '';
      }
      requestAnimationFrame(function () { requestAnimationFrame(sweep); });
      window.setTimeout(sweep, 200);
      window.setTimeout(sweep, 800);
    });
  }

  function initAdvisor360ActivityFilters() {
    var list = document.getElementById('a360ActivityList');
    var typeF = document.getElementById('a360ActivityType');
    var rangeF = document.getElementById('a360ActivityRange');
    var clearBtn = document.getElementById('a360ActivityClear');
    var empty = document.getElementById('a360ActivityEmpty');
    if (!list || !typeF || !rangeF) return;

    function apply() {
      var kind = typeF.value;
      var days = parseInt(rangeF.value || '0', 10);
      var cutoff = days > 0 ? (Date.now() / 1000) - (days * 86400) : 0;
      var visible = 0;
      list.querySelectorAll('.a360-timeline__item').forEach(function (item) {
        var matchKind = !kind || item.getAttribute('data-kind') === kind;
        var ts = parseInt(item.getAttribute('data-ts') || '0', 10);
        var matchRange = !cutoff || ts >= cutoff;
        var show = matchKind && matchRange;
        item.style.display = show ? '' : 'none';
        if (show) visible++;
      });
      if (empty) empty.hidden = visible > 0;
      list.hidden = visible === 0;
      if (clearBtn) clearBtn.hidden = !kind && !days;
    }

    function reset() {
      typeF.value = '';
      rangeF.value = '';
      apply();
    }

    typeF.addEventListener('change', apply);
    rangeF.addEventListener('change', apply);
    if (clearBtn) clearBtn.addEventListener('click', reset);
    apply();
  }

  function initAdvisor360ExportMenus() {
    document.querySelectorAll('.a360-export').forEach(function (wrap) {
      wrap.addEventListener('toggle', function () {
        if (!wrap.open) return;
        document.querySelectorAll('.a360-export[open]').forEach(function (other) {
          if (other !== wrap) other.open = false;
        });
      });
    });
    document.addEventListener('click', function (e) {
      if (e.target.closest('.a360-export')) return;
      document.querySelectorAll('.a360-export[open]').forEach(function (el) {
        el.open = false;
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initAgencyInviteModal();
    initInvitePhonePreview();
    initModalInvitePreview();
    initStickyStepFooter();
    initNavScrollHint();
    initMemberFilters();
    initAdvisor360Search();
    initAdvisor360ActivityFilters();
    initAdvisor360ExportMenus();
  });
})();
