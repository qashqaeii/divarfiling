(function () {
  function csrf() {
    const c = document.cookie.match(/csrftoken=([^;]+)/);
    return c ? c[1] : '';
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      credentials: 'same-origin',
      body: JSON.stringify(body || {}),
    }).then((r) => r.json());
  }

  function patchJson(url, body) {
    return fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      credentials: 'same-origin',
      body: JSON.stringify(body || {}),
    }).then((r) => r.json());
  }

  function portalModalToBody(id) {
    const el = typeof id === 'string' ? document.getElementById(id) : id;
    if (!el || el.parentElement === document.body) return el;
    document.body.appendChild(el);
    return el;
  }

  function openModal(id) {
    const el = typeof id === 'string' ? document.getElementById(id) : id;
    if (!el) return;
    if (typeof window.WSModal !== 'undefined' && window.WSModal.open) {
      window.WSModal.open(el.id || id);
      return;
    }
    el.hidden = false;
    el.classList.add('is-open');
    document.body.classList.add('ws-modal-open');
  }

  function closeModal(el) {
    const modal = typeof el === 'string' ? document.getElementById(el) : el;
    if (!modal) return;
    if (typeof window.WSModal !== 'undefined' && window.WSModal.close) {
      window.WSModal.close(modal);
      return;
    }
    modal.hidden = true;
    modal.classList.remove('is-open');
    document.body.classList.remove('ws-modal-open');
  }

  function prefillSpacePublishForm(config) {
    const form = document.getElementById('agency-space-publish-form');
    if (!form || !config || !form.dataset.itemId) return;
    const visibility = config.visibility;
    if (visibility) {
      const visEl = form.querySelector(`input[name="visibility"][value="${visibility}"]`);
      if (visEl) visEl.checked = true;
    }
    const csl = config.contact_share_level;
    if (csl) {
      const cslEl = form.querySelector(`input[name="contact_share_level"][value="${csl}"]`);
      if (cslEl) cslEl.checked = true;
    }
    const noteEl = form.querySelector('[name="note"]');
    if (noteEl && config.note != null) noteEl.value = config.note;
    const memberIds = Array.isArray(config.member_ids) ? config.member_ids : [];
    form.querySelectorAll('input[name="member_ids"]').forEach((cb) => {
      cb.checked = memberIds.indexOf(parseInt(cb.value, 10)) !== -1;
    });
    const audience = document.getElementById('agency-space-audience');
    const visChecked = form.querySelector('input[name="visibility"]:checked')?.value;
    if (audience) audience.hidden = visChecked !== 'selected_members';
  }

  function readEditConfig() {
    const el = document.getElementById('agency-space-edit-config');
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function initSpaceExpandFilters() {
    const filterPanel = document.getElementById('agency-space-filters-panel');
    const filterToggle = document.getElementById('agencySpaceAdvToggle');
    if (!filterPanel || filterPanel.dataset.bound === '1') return;
    filterPanel.dataset.bound = '1';

    const setOpen = (open) => {
      if (filterToggle) {
        filterToggle.classList.toggle('is-open', open);
        filterToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      }
      filterPanel.classList.toggle('is-open', open);
      if (open) {
        filterPanel.removeAttribute('hidden');
        if (typeof initCRMJalaliPickers === 'function') {
          initCRMJalaliPickers(filterPanel);
        }
        if (typeof initCRMMoneyInputs === 'function') {
          initCRMMoneyInputs(document.getElementById('agency-space-list-form') || filterPanel);
        }
      } else {
        filterPanel.setAttribute('hidden', '');
      }
    };

    filterToggle?.addEventListener('click', () => {
      setOpen(!filterPanel.classList.contains('is-open'));
    });

    if (filterPanel.classList.contains('is-open')) {
      if (typeof initCRMJalaliPickers === 'function') {
        initCRMJalaliPickers(filterPanel);
      }
      if (typeof initCRMMoneyInputs === 'function') {
        initCRMMoneyInputs(document.getElementById('agency-space-list-form') || filterPanel);
      }
    }

    filterPanel.addEventListener('change', (e) => {
      const input = e.target;
      if (!input.classList || !input.classList.contains('agency-space-team-pick__input')) return;
      filterPanel.querySelectorAll('.agency-space-team-pick__item').forEach((item) => {
        item.classList.toggle('is-selected', !!item.querySelector('.agency-space-team-pick__input:checked'));
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    ['modal-space-gallery', 'modal-space-moderate', 'modal-agency-space-publish'].forEach((modalId) => {
      portalModalToBody(modalId);
    });

    initSpaceExpandFilters();

    const listForm = document.getElementById('agency-space-list-form');
    if (listForm && typeof initCRMMoneyInputs === 'function') {
      initCRMMoneyInputs(listForm);
    }
    const orderingSelect = listForm?.querySelector('[name="ordering"]');
    if (listForm && orderingSelect) {
      orderingSelect.addEventListener('change', () => {
        if (typeof listForm.requestSubmit === 'function') {
          listForm.requestSubmit();
        } else {
          listForm.submit();
        }
      });
    }

    document.querySelectorAll('[data-modal-close]').forEach((btn) => {
      btn.addEventListener('click', function () {
        const modal = btn.closest('.ws-modal');
        closeModal(modal);
      });
    });

    const form = document.getElementById('agency-space-publish-form');
    if (form) {
      const editConfig = readEditConfig();
      if (editConfig) prefillSpacePublishForm(editConfig);
      const audience = document.getElementById('agency-space-audience');
      form.querySelectorAll('input[name="visibility"]').forEach((el) => {
        el.addEventListener('change', function () {
          if (!audience) return;
          audience.hidden = form.querySelector('input[name="visibility"]:checked')?.value !== 'selected_members';
        });
      });
      document.querySelectorAll('[data-space-edit-publication]').forEach((btn) => {
        btn.addEventListener('click', function () {
          if (editConfig) prefillSpacePublishForm(editConfig);
        });
      });
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        const kind = form.dataset.sourceKind;
        const visibility = form.querySelector('input[name="visibility"]:checked')?.value;
        const memberIds = Array.from(form.querySelectorAll('input[name="member_ids"]:checked')).map((x) => parseInt(x.value, 10));
        const note = (form.querySelector('[name="note"]')?.value || '').trim();
        const itemId = form.dataset.itemId;
        const base = window.AGENCY_SPACE_API || {};
        if (itemId) {
          patchJson(base.itemUrl || `/workspace/api/crm/agency/space/items/${itemId}/`, {
            visibility,
            member_ids: memberIds,
            contact_share_level: form.querySelector('input[name="contact_share_level"]:checked')?.value,
            note,
          }).then((res) => {
            if (res.ok) window.location.reload();
            else alert(res.error || 'خطا');
          });
          return;
        }
        const url = kind === 'customer'
          ? (base.publishContact || '/workspace/api/crm/agency/space/publish/contact/')
          : (base.publishProperty || '/workspace/api/crm/agency/space/publish/property/');
        const payload = {
          visibility,
          member_ids: memberIds,
          note,
          contact_share_level: form.querySelector('input[name="contact_share_level"]:checked')?.value,
        };
        if (kind === 'customer') payload.customer_id = parseInt(form.dataset.customerId, 10);
        else payload.property_id = parseInt(form.dataset.propertyId, 10);
        postJson(url, payload).then((res) => {
          if (res.ok) window.location.reload();
          else alert(res.error || 'خطا');
        });
      });
    }

    function promoteCopyButton(btn, targetUrl) {
      document.querySelectorAll(`[data-space-copy][data-item-id="${btn.dataset.itemId}"]`).forEach((b) => {
        b.remove();
      });
      const card = btn.closest('.agency-space-card');
      if (card) {
        const link = document.createElement('a');
        link.href = targetUrl;
        link.className = 'agency-space-property-card__btn agency-space-property-card__btn--primary agency-space-card__btn agency-space-card__btn--primary';
        link.setAttribute('data-space-crm-link', '');
        link.textContent = 'باز کردن CRM';
        const actions = card.querySelector('.agency-space-property-card__actions, .agency-space-card__actions');
        if (actions) actions.appendChild(link);
        const trail = card.querySelector('.agency-space-property-card__trail');
        if (trail && !card.querySelector('.agency-space-property-card__crm-state')) {
          const p = document.createElement('p');
          p.className = 'agency-space-property-card__crm-state';
          p.innerHTML = '<i class="fas fa-circle-check" aria-hidden="true"></i>در CRM من';
          trail.appendChild(p);
        } else {
          const row = card.querySelector('.agency-space-card__meta-row');
          if (row && !card.querySelector('.agency-space-card__crm-flag')) {
            const span = document.createElement('span');
            span.className = 'agency-space-card__crm-flag';
            span.innerHTML = '<i class="fas fa-circle-check" aria-hidden="true"></i>در CRM من';
            row.appendChild(span);
          }
        }
      }
      const detail = document.querySelector('.agency-space-detail');
      if (detail) {
        detail.querySelectorAll('.agency-space-detail__sticky-primary[data-space-copy]').forEach((el) => el.remove());
        const sticky = detail.querySelector('.agency-space-detail__sticky-inner');
        if (sticky && !sticky.querySelector('.agency-space-detail__sticky-primary')) {
          const stickyLink = document.createElement('a');
          stickyLink.href = targetUrl;
          stickyLink.className = 'crm-btn crm-btn-primary crm-btn-sm agency-space-detail__sticky-primary';
          stickyLink.textContent = 'مشاهده در CRM';
          sticky.appendChild(stickyLink);
        }
        const crmBody = detail.querySelector('.agency-space-detail__aside-card--crm .agency-space-detail__aside-body');
        if (crmBody) {
          crmBody.innerHTML = '<p class="agency-space-detail__crm-ok"><i class="fas fa-circle-check" aria-hidden="true"></i> ذخیره در CRM شما</p>';
          const a = document.createElement('a');
          a.href = targetUrl;
          a.className = 'crm-btn crm-btn-primary crm-btn-sm crm-btn-block';
          a.textContent = 'مشاهده نسخه من';
          crmBody.appendChild(a);
        }
      }
    }

    document.querySelectorAll('[data-space-copy]').forEach((btn) => {
      btn.addEventListener('click', function () {
        const id = btn.dataset.itemId;
        if (!id || btn.disabled || btn.dataset.copying === '1') return;
        const card = btn.closest('.agency-space-card');
        if (card && card.querySelector('[data-space-crm-link]')) return;
        btn.dataset.copying = '1';
        btn.disabled = true;
        postJson(`/workspace/api/crm/agency/space/items/${id}/copy/`, {}).then((res) => {
          if (res.ok && res.data && res.data.target_url) {
            promoteCopyButton(btn, res.data.target_url);
          } else {
            btn.disabled = false;
            btn.dataset.copying = '0';
            alert(res.error || 'خطا در کپی');
          }
        }).catch(() => {
          btn.disabled = false;
          btn.dataset.copying = '0';
          alert('خطا در ارتباط');
        });
      });
    });

    const grid = document.querySelector('[data-space-grid]');
    const viewBtns = document.querySelectorAll('[data-space-view]');
    const viewKey = 'agency-space-view-mode';
    function setView(mode) {
      if (!grid) return;
      grid.classList.toggle('is-list-view', mode === 'list');
      viewBtns.forEach((b) => {
        b.classList.toggle('is-active', b.dataset.spaceView === mode);
      });
      try {
        localStorage.setItem(viewKey, mode);
      } catch (e) { /* ignore */ }
    }
    viewBtns.forEach((b) => {
      b.addEventListener('click', function () {
        setView(b.dataset.spaceView || 'grid');
      });
    });
    try {
      const saved = localStorage.getItem(viewKey);
      if (saved === 'list' || saved === 'grid') setView(saved);
    } catch (e) { /* ignore */ }

    const detail = document.querySelector('.agency-space-detail');
    if (detail) {
      const main = detail.querySelector('[data-space-gallery-main]');
      const lightboxImg = document.getElementById('agency-space-lightbox-img');
      const setActiveImage = (src, activeBtn) => {
        if (!src) return;
        if (main) main.src = src;
        if (lightboxImg) lightboxImg.src = src;
        detail.querySelectorAll('[data-space-gallery-thumb]').forEach((b) => b.classList.remove('is-active'));
        if (activeBtn) activeBtn.classList.add('is-active');
      };
      detail.querySelectorAll('[data-space-gallery-thumb]').forEach((btn) => {
        btn.addEventListener('click', function () {
          setActiveImage(btn.dataset.src, btn);
        });
      });
      detail.querySelectorAll('[data-space-gallery-lightbox]').forEach((btn) => {
        btn.addEventListener('click', function () {
          const src = main?.src || btn.querySelector('img')?.src;
          if (lightboxImg && src) lightboxImg.src = src;
          openModal('modal-space-gallery');
        });
      });
    }

    if (detail) {
      const itemId = detail.dataset.itemId;
      const unpublish = detail.querySelector('[data-space-unpublish]');
      if (unpublish) {
        unpublish.addEventListener('click', function () {
          postJson(`/workspace/api/crm/agency/space/items/${itemId}/unpublish/`, {}).then((res) => {
            if (res.ok) window.location.href = '/workspace/crm/agency/space/';
            else alert(res.error || 'خطا');
          });
        });
      }
      const moderateUrl = detail.dataset.moderateUrl
        || `/workspace/api/crm/agency/space/items/${itemId}/moderate/`;
      const modHide = detail.querySelector('[data-space-moderate-hide]');
      const modForm = document.getElementById('agency-space-moderate-form');
      if (modHide) {
        modHide.addEventListener('click', function () {
          if (document.getElementById('modal-space-moderate')) {
            openModal('modal-space-moderate');
          } else {
            postJson(moderateUrl, { action: 'hide' }).then((res) => {
              if (res.ok) window.location.href = '/workspace/crm/agency/space/';
              else alert(res.error || 'خطا');
            });
          }
        });
      }
      if (modForm) {
        modForm.addEventListener('submit', function (e) {
          e.preventDefault();
          const preset = modForm.querySelector('[name="reason_preset"]')?.value || '';
          const text = (modForm.querySelector('[name="reason_text"]')?.value || '').trim();
          const reason = text || preset;
          postJson(moderateUrl, { action: 'hide', reason }).then((res) => {
            if (res.ok) window.location.href = '/workspace/crm/agency/space/';
            else alert(res.error || 'خطا');
          });
        });
      }
      const modRestore = detail.querySelector('[data-space-moderate-restore]');
      if (modRestore) {
        modRestore.addEventListener('click', function () {
          postJson(moderateUrl, { action: 'restore' }).then((res) => {
            if (res.ok) window.location.reload();
            else alert(res.error || 'خطا');
          });
        });
      }
    }
  });
})();
