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
      function rtlScrollMax() {
        return Math.max(0, track.scrollWidth - track.clientWidth);
      }

      function revealRtlOverflow() {
        if (getComputedStyle(track).direction !== 'rtl') return;
        var max = rtlScrollMax();
        if (max < 2) return;
        /* RTL horizontal scroll: default position can clip inline-start (e.g. تنظیمات). */
        if (track.scrollLeft === 0) {
          track.scrollLeft = -max;
        }
        if (track.scrollLeft > 0 && track.scrollLeft < max - 1) {
          track.scrollLeft = max;
        }
      }

      function update() {
        var max = rtlScrollMax();
        var sl = track.scrollLeft;
        var atEnd;
        var atStart;
        if (getComputedStyle(track).direction === 'rtl' && sl <= 0) {
          atEnd = Math.abs(sl) >= max - 8;
          atStart = Math.abs(sl) < 8;
        } else {
          atEnd = max - sl < 8;
          atStart = sl < 8;
        }
        track.classList.toggle('is-scroll-end', atEnd);
        track.classList.toggle('is-scroll-start', atStart);
      }
      track.addEventListener('scroll', update, { passive: true });
      revealRtlOverflow();
      update();
      window.addEventListener('resize', function () {
        revealRtlOverflow();
        update();
      }, { passive: true });
    });
  }

  var SEARCH_GUARD_SELECTOR = [
    '#agencyMemberSearch',
    '.a360-search-input',
    '[data-msg-search]',
    '[data-ann-search]',
    '[data-audit-search]',
    '.crm-msg-search input',
    '.crm-ann-search input',
    '.crm-audit-search input',
  ].join(',');

  function guardSearchInput(input) {
    if (!input || input.dataset.searchAutofillGuard === '1') return;
    input.dataset.searchAutofillGuard = '1';
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('autocorrect', 'off');
    input.setAttribute('autocapitalize', 'off');
    input.setAttribute('spellcheck', 'false');
    input.setAttribute('data-lpignore', 'true');
    input.setAttribute('data-1p-ignore', 'true');
    input.setAttribute('data-form-type', 'other');
    if (!input.getAttribute('role')) input.setAttribute('role', 'searchbox');
    if (!input.name || input.name === 'phone' || input.name === 'tel' || input.name === 'mobile') {
      if (input.hasAttribute('data-msg-search')) input.name = 'mk_team_msg_filter_q';
      else if (input.hasAttribute('data-ann-search')) input.name = 'mk_team_ann_filter_q';
      else if (input.hasAttribute('data-audit-search')) input.name = 'mk_team_audit_filter_q';
      else input.name = 'mk_filter_q';
    }
    input.setAttribute('readonly', 'readonly');
    input.addEventListener('focus', function () {
      input.removeAttribute('readonly');
    }, { once: true });
  }

  function guardMemberSearchInput(input) {
    guardSearchInput(input);
  }

  function clearPhoneAutofill(input) {
    var value = (input.value || '').trim();
    if (!value || !IR_MOBILE.test(normalizePhone(value))) return false;
    input.value = '';
    return true;
  }

  function sweepSearchAutofill(input, userEdited) {
    if (!input || (userEdited && userEdited.current)) return false;
    if (!clearPhoneAutofill(input)) return false;
    try {
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } catch (e) { /* ignore */ }
    return true;
  }

  function bindSearchAutofillGuard(input) {
    if (!input) return;
    guardSearchInput(input);
    var userEdited = { current: !!input.value.trim() };
    input.addEventListener('input', function () { userEdited.current = true; });
    function sweep() { sweepSearchAutofill(input, userEdited); }
    var msgHub = input.closest('[data-crm-messages]');
    if (msgHub) {
      msgHub.addEventListener('crm-msg-threads-loaded', sweep, { once: true });
      window.setTimeout(sweep, 3000);
    } else {
      sweep();
      requestAnimationFrame(function () { requestAnimationFrame(sweep); });
      window.setTimeout(sweep, 120);
      window.setTimeout(sweep, 500);
      window.setTimeout(sweep, 1000);
      window.setTimeout(sweep, 2000);
    }
  }

  function initSearchAutofillGuards() {
    document.querySelectorAll(SEARCH_GUARD_SELECTOR).forEach(bindSearchAutofillGuard);
  }

  function initAgencyMembersFilterSheet() {
    var openBtn = document.getElementById('agencyMemberFilterOpen');
    var panel = document.getElementById('agencyMemberFilterPanel');
    var backdrop = document.getElementById('agencyMemberFilterBackdrop');
    if (!openBtn || !panel) return;

    function setOpen(open) {
      document.body.classList.toggle('agency-members-filter-open', open);
      openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    openBtn.addEventListener('click', function () {
      setOpen(true);
    });
    document.querySelectorAll('[data-agency-members-filter-close]').forEach(function (el) {
      el.addEventListener('click', function () { setOpen(false); });
    });
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && document.body.classList.contains('agency-members-filter-open')) {
        setOpen(false);
      }
    });
  }

  function initMemberFilters() {
    var search = document.getElementById('agencyMemberSearch');
    var statusF = document.getElementById('agencyMemberStatusFilter');
    var roleF = document.getElementById('agencyMemberRoleFilter');
    var licenseF = document.getElementById('agencyMemberLicenseFilter');
    var sortF = document.getElementById('agencyMemberSort');
    var clearBtn = document.getElementById('agencyMemberFilterClear');
    var badge = document.getElementById('agencyMemberFilterBadge');
    var empty = document.getElementById('agencyMembersFilterEmpty');
    if (!search) return;

    guardMemberSearchInput(search);

    var userEdited = false;

    function activeFilterCount() {
      var n = 0;
      if (statusF && statusF.value) n++;
      if (roleF && roleF.value) n++;
      if (licenseF && licenseF.value) n++;
      if (sortF && sortF.value && sortF.value !== 'name') n++;
      return n;
    }

    function hasActiveFilters() {
      return !!(search.value.trim() || activeFilterCount());
    }

    function updateClearBtn() {
      if (clearBtn) clearBtn.hidden = !hasActiveFilters();
      if (badge) {
        var n = activeFilterCount();
        if (n > 0) {
          badge.hidden = false;
          badge.textContent = String(n);
        } else {
          badge.hidden = true;
        }
      }
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
      var role = roleF ? roleF.value : '';
      var lic = licenseF ? licenseF.value : '';
      document.querySelectorAll('#agencyMembersTable tbody tr[data-name], .agency-member-card[data-name]').forEach(function (el) {
        var name = el.getAttribute('data-name') || '';
        var phone = el.getAttribute('data-phone') || '';
        var matchQ = !q || name.indexOf(q) !== -1 || phone.indexOf(q) !== -1;
        var matchS = !st || el.getAttribute('data-status') === st;
        var matchR = !role || el.getAttribute('data-role') === role;
        var matchL = !lic || el.getAttribute('data-license') === lic;
        el.style.display = matchQ && matchS && matchR && matchL ? '' : 'none';
      });
      updateClearBtn();
      checkEmpty();
    }

    function resetFilters() {
      userEdited = false;
      search.value = '';
      if (statusF) statusF.value = '';
      if (roleF) roleF.value = '';
      if (licenseF) licenseF.value = '';
      if (sortF) sortF.value = 'name';
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
    if (roleF) roleF.addEventListener('change', filterMembers);
    if (licenseF) licenseF.addEventListener('change', filterMembers);
    if (sortF) sortF.addEventListener('change', filterMembers);
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
    initSearchAutofillGuards();
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

  function initAgencyHubNavMoreSheet() {
    var sheet = document.getElementById('agencyHubNavSheet');
    var openBtn = document.getElementById('agencyHubNavMoreBtn');
    if (!sheet || !openBtn) return;

    var mq = window.matchMedia('(max-width: 767px)');

    function setOpen(open) {
      if (!mq.matches) {
        sheet.hidden = true;
        sheet.classList.remove('is-open');
        sheet.setAttribute('aria-hidden', 'true');
        openBtn.setAttribute('aria-expanded', 'false');
        document.body.classList.remove('agency-hub-nav-sheet-open');
        return;
      }
      sheet.hidden = !open;
      sheet.classList.toggle('is-open', open);
      sheet.setAttribute('aria-hidden', open ? 'false' : 'true');
      openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      document.body.classList.toggle('agency-hub-nav-sheet-open', open);
    }

    openBtn.addEventListener('click', function () {
      setOpen(!sheet.classList.contains('is-open'));
    });

    sheet.querySelectorAll('[data-agency-hub-nav-more-close]').forEach(function (el) {
      el.addEventListener('click', function () {
        setOpen(false);
      });
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sheet.classList.contains('is-open')) {
        e.preventDefault();
        setOpen(false);
      }
    }, true);

    mq.addEventListener?.('change', function () {
      if (!mq.matches) setOpen(false);
    });
  }

  function initMemberPermissionsSheet() {
    var sheet = document.getElementById('agencyMemberPermsSheet');
    var form = document.getElementById('agencyMemberPermsForm');
    var presetForm = document.getElementById('agencyMemberPermsPresetForm');
    if (!sheet || !form) return;

    var memberIdInput = document.getElementById('agencyMemberPermsMemberId');
    var presetMemberId = document.getElementById('agencyMemberPermsPresetMemberId');
    var presetValue = document.getElementById('agencyMemberPermsPresetValue');
    var subtitle = document.getElementById('agencyMemberPermsSubtitle');
    var effectiveEl = document.getElementById('agencyMemberPermsEffective');
    var dirtyEl = document.getElementById('agencyMemberPermsDirty');
    var checkboxes = form.querySelectorAll('input[data-perm-code]');
    var initialState = '';

    function permState() {
      return Array.prototype.map.call(checkboxes, function (cb) {
        return cb.getAttribute('data-perm-code') + ':' + (cb.checked ? '1' : '0');
      }).join(';');
    }

    function updateDirty() {
      var dirty = initialState && permState() !== initialState;
      if (dirtyEl) dirtyEl.hidden = !dirty;
    }

    function setOpen(open) {
      sheet.hidden = !open;
      sheet.setAttribute('aria-hidden', open ? 'false' : 'true');
      document.body.classList.toggle('agency-perms-sheet-open', open);
      if (!open) initialState = '';
    }

    function fillForm(permsSet) {
      checkboxes.forEach(function (cb) {
        var code = cb.getAttribute('data-perm-code');
        cb.checked = permsSet.indexOf(code) !== -1;
      });
      initialState = permState();
      updateDirty();
    }

    function openForButton(btn) {
      var id = btn.getAttribute('data-member-id');
      var name = btn.getAttribute('data-member-name') || '';
      var labels = btn.getAttribute('data-effective-labels') || '';
      var permsRaw = btn.getAttribute('data-perms') || '';
      var perms = permsRaw ? permsRaw.split(',').filter(Boolean) : [];
      if (memberIdInput) memberIdInput.value = id || '';
      if (presetMemberId) presetMemberId.value = id || '';
      if (subtitle) subtitle.textContent = name;
      if (effectiveEl) {
        if (labels) {
          effectiveEl.textContent = 'مجوز مؤثر: ' + labels.replace(/\|/g, ' · ');
          effectiveEl.hidden = false;
        } else {
          effectiveEl.hidden = true;
        }
      }
      fillForm(perms);
      setOpen(true);
    }

    document.querySelectorAll('.js-agency-perms-open').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openForButton(btn);
      });
    });

    sheet.querySelectorAll('[data-agency-perms-close]').forEach(function (el) {
      el.addEventListener('click', function () {
        if (dirtyEl && !dirtyEl.hidden) {
          if (!window.confirm('تغییرات ذخیره نشده‌اند. بسته شود؟')) return;
        }
        setOpen(false);
      });
    });

    checkboxes.forEach(function (cb) {
      cb.addEventListener('change', updateDirty);
    });

    form.addEventListener('submit', function (e) {
      var sensitive = ['finance.view', 'contracts.view_team', 'deals.view_team', 'licenses.manage'];
      var toggledSensitive = false;
      checkboxes.forEach(function (cb) {
        var code = cb.getAttribute('data-perm-code');
        if (sensitive.indexOf(code) === -1) return;
        var was = initialState.indexOf(code + ':1') !== -1;
        if (cb.checked !== was) toggledSensitive = true;
      });
      if (toggledSensitive && !window.confirm('مجوزهای حساس تغییر می‌کند. تأیید می‌کنید؟')) {
        e.preventDefault();
      }
    });

    sheet.querySelectorAll('[data-agency-perms-preset]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var preset = btn.getAttribute('data-agency-perms-preset');
        if (!presetMemberId || !presetValue || !presetForm) return;
        if (!window.confirm('الگوی نقش اعمال شود؟ مجوزهای سفارشی بازنشانی می‌شوند.')) return;
        presetValue.value = preset;
        presetForm.requestSubmit();
      });
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !sheet.hidden) {
        e.preventDefault();
        setOpen(false);
      }
    }, true);
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
    initAgencyHubNavMoreSheet();
    initAgencyInviteModal();
    initInvitePhonePreview();
    initModalInvitePreview();
    initStickyStepFooter();
    initNavScrollHint();
    initAgencyMembersFilterSheet();
    initMemberPermissionsSheet();
    initMemberFilters();
    initSearchAutofillGuards();
    initAdvisor360ActivityFilters();
    initAdvisor360ExportMenus();
  });
})();
