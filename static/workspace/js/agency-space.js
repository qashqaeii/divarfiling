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

  function setFiltersOpen(open) {
    const filterPanel = document.getElementById('agency-space-filters-panel');
    const filterToggle = document.querySelector('[data-space-filters-open]');
    const backdrop = document.getElementById('agency-space-filters-backdrop');
    if (!filterPanel) return;
    filterPanel.hidden = !open;
    if (filterToggle) {
      filterToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      filterToggle.classList.toggle('is-active', open);
    }
    if (backdrop) {
      backdrop.hidden = !open;
      backdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
    }
    document.body.classList.toggle('agency-space-filters-open', open);
  }

  document.addEventListener('DOMContentLoaded', function () {
    const filterToggle = document.querySelector('[data-space-filters-open]');
    const filterPanel = document.getElementById('agency-space-filters-panel');
    const backdrop = document.getElementById('agency-space-filters-backdrop');
    if (filterToggle && filterPanel) {
      filterToggle.addEventListener('click', function () {
        setFiltersOpen(filterPanel.hidden);
      });
    }
    document.querySelectorAll('[data-space-filters-close]').forEach((btn) => {
      btn.addEventListener('click', function () {
        setFiltersOpen(false);
      });
    });
    if (backdrop) {
      backdrop.addEventListener('click', function () {
        setFiltersOpen(false);
      });
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && filterPanel && !filterPanel.hidden) {
        setFiltersOpen(false);
      }
    });

    document.querySelectorAll('[data-modal-close]').forEach((btn) => {
      btn.addEventListener('click', function () {
        const modal = btn.closest('.ws-modal');
        closeModal(modal);
      });
    });

    const form = document.getElementById('agency-space-publish-form');
    if (form) {
      const audience = document.getElementById('agency-space-audience');
      form.querySelectorAll('input[name="visibility"]').forEach((el) => {
        el.addEventListener('change', function () {
          if (!audience) return;
          audience.hidden = form.querySelector('input[name="visibility"]:checked')?.value !== 'selected_members';
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

    document.querySelectorAll('[data-space-copy]').forEach((btn) => {
      btn.addEventListener('click', function () {
        const id = btn.dataset.itemId;
        if (!id) return;
        btn.disabled = true;
        postJson(`/workspace/api/crm/agency/space/items/${id}/copy/`, {}).then((res) => {
          if (res.ok && res.data && res.data.target_url) {
            if (res.data.already_copied) {
              window.location.href = res.data.target_url;
            } else {
              window.location.href = res.data.target_url;
            }
          } else {
            btn.disabled = false;
            alert(res.error || 'خطا در کپی');
          }
        }).catch(() => {
          btn.disabled = false;
          alert('خطا در ارتباط');
        });
      });
    });

    const detail = document.querySelector('.agency-space-detail');
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
