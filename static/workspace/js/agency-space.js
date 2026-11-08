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

  function initSpaceOrderingSync() {
    const desk = document.querySelector('[data-space-ordering-desk]');
    const mob = document.querySelector('[data-space-ordering-mob]');
    if (!desk || !mob) return;
    const mq = window.matchMedia('(max-width: 767px)');
    const syncDisabled = () => {
      const mobile = mq.matches;
      desk.disabled = mobile;
      mob.disabled = !mobile;
      if (mobile && mob.value !== desk.value) mob.value = desk.value;
      if (!mobile && desk.value !== mob.value) desk.value = mob.value;
    };
    const onChange = (from, to) => {
      if (!from || !to || from.disabled) return;
      to.value = from.value;
    };
    desk.addEventListener('change', () => onChange(desk, mob));
    mob.addEventListener('change', () => onChange(mob, desk));
    syncDisabled();
    mq.addEventListener?.('change', syncDisabled);
  }

  function initSpaceExpandFilters() {
    const filterPanel = document.getElementById('agency-space-filters-panel');
    const filterToggle = document.getElementById('agencySpaceAdvToggle');
    const backdrop = document.getElementById('agencySpaceFilterBackdrop');
    if (!filterPanel || filterPanel.dataset.bound === '1') return;
    filterPanel.dataset.bound = '1';

    const mq = window.matchMedia('(max-width: 767px)');

    const setOpen = (open) => {
      if (filterToggle) {
        filterToggle.classList.toggle('is-open', open);
        filterToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      }
      filterPanel.classList.toggle('is-open', open);
      if (open) {
        filterPanel.removeAttribute('hidden');
        if (backdrop) {
          backdrop.hidden = false;
          backdrop.setAttribute('aria-hidden', 'false');
        }
        if (mq.matches) {
          document.body.classList.add('agency-space-filter-open');
        }
        if (typeof initCRMJalaliPickers === 'function') {
          initCRMJalaliPickers(filterPanel);
        }
        if (typeof initCRMMoneyInputs === 'function') {
          initCRMMoneyInputs(document.getElementById('agency-space-list-form') || filterPanel);
        }
      } else {
        filterPanel.setAttribute('hidden', '');
        if (backdrop) {
          backdrop.hidden = true;
          backdrop.setAttribute('aria-hidden', 'true');
        }
        document.body.classList.remove('agency-space-filter-open');
      }
    };

    const close = () => setOpen(false);

    filterToggle?.addEventListener('click', () => {
      setOpen(!filterPanel.classList.contains('is-open'));
    });

    backdrop?.addEventListener('click', close);
    filterPanel.querySelectorAll('[data-space-filter-close]').forEach((el) => {
      el.addEventListener('click', close);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && filterPanel.classList.contains('is-open') && mq.matches) {
        e.preventDefault();
        e.stopImmediatePropagation();
        close();
      }
    }, true);

    const listForm = document.getElementById('agency-space-list-form');
    listForm?.addEventListener('submit', () => {
      if (mq.matches && filterPanel.classList.contains('is-open')) close();
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
    initSpaceOrderingSync();
    initSpaceSearchClear();

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

    function isElementVisible(el) {
      if (!el || el.hidden) return false;
      const st = window.getComputedStyle(el);
      return st.display !== 'none' && st.visibility !== 'hidden';
    }

    function getVisibleSpaceActionBlocks(card) {
      return Array.from(
        card.querySelectorAll(
          '.agency-space-property-card__actions, .agency-space-contact-card__actions, .agency-space-card__actions',
        ),
      ).filter(isElementVisible);
    }

    function initSpaceSearchClear() {
      const field = document.querySelector('.agency-space-toolbar__search');
      const input = field?.querySelector('input[name="q"]');
      if (!field || !input) return;
      let clearBtn = field.querySelector('[data-space-search-clear]');
      if (!clearBtn) {
        clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'agency-space-search__clear';
        clearBtn.setAttribute('data-space-search-clear', '');
        clearBtn.setAttribute('aria-label', 'پاک کردن جستجو');
        clearBtn.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';
        field.appendChild(clearBtn);
      }
      const syncClear = () => {
        const hasValue = Boolean((input.value || '').trim());
        clearBtn.hidden = !hasValue;
        field.classList.toggle('agency-space-search__field--has-value', hasValue);
      };
      clearBtn.addEventListener('click', () => {
        input.value = '';
        syncClear();
        input.focus();
        const form = input.closest('form');
        if (form) {
          if (typeof form.requestSubmit === 'function') form.requestSubmit();
          else form.submit();
        }
      });
      input.addEventListener('input', syncClear);
      syncClear();
    }

    function detailIsContact(detailRoot) {
      if (!detailRoot) return false;
      return Boolean(
        detailRoot.querySelector('.agency-space-contact-detail')
        || detailRoot.querySelector('.agency-space-detail__layout--contact'),
      );
    }

    function fillCrmSuccessPanel(container, targetUrl, isContact, linkClass) {
      container.textContent = '';
      const status = document.createElement('p');
      status.className = 'agency-space-pro-status agency-space-pro-status--ok';
      status.innerHTML = isContact
        ? '<i class="fas fa-circle-check" aria-hidden="true"></i> این مخاطب در CRM شماست'
        : '<i class="fas fa-circle-check" aria-hidden="true"></i> این فایل در CRM شماست';
      const link = document.createElement('a');
      link.href = targetUrl;
      link.className = linkClass;
      link.setAttribute('data-space-crm-link', '');
      link.textContent = isContact ? 'باز کردن مخاطب در CRM' : 'باز کردن CRM';
      container.appendChild(status);
      container.appendChild(link);
    }

    function renderDetailCrmSuccess(detail, targetUrl, isContact) {
      detail.querySelectorAll('[data-space-crm-panel]').forEach((panel) => {
        fillCrmSuccessPanel(panel, targetUrl, isContact, 'agency-space-pro-btn agency-space-pro-btn--primary crm-btn-block');
      });
      detail.querySelectorAll('.agency-space-property-detail__aside-card--crm .agency-space-property-detail__aside-body, .agency-space-contact-detail__aside-card--crm .agency-space-contact-detail__aside-body, .agency-space-detail__aside-card--crm .agency-space-detail__aside-body').forEach((body) => {
        if (body.hasAttribute('data-space-crm-panel')) return;
        fillCrmSuccessPanel(body, targetUrl, isContact, 'crm-btn crm-btn-primary crm-btn-sm crm-btn-block');
      });
    }

    function promoteCopyButton(btn, targetUrl) {
      const itemId = btn.dataset.itemId;
      document.querySelectorAll(`[data-space-copy][data-item-id="${itemId}"]`).forEach((b) => {
        b.remove();
      });
      const card = btn.closest('.agency-space-card');
      if (card) {
        card.querySelectorAll('[data-space-crm-link]').forEach((a) => a.remove());
        const link = document.createElement('a');
        link.href = targetUrl;
        const isContact = card.classList.contains('agency-space-contact-card');
        link.className = isContact
          ? 'agency-space-contact-card__btn agency-space-contact-card__btn--primary'
          : 'agency-space-property-card__btn agency-space-property-card__btn--primary agency-space-card__btn agency-space-card__btn--primary';
        link.setAttribute('data-space-crm-link', '');
        link.innerHTML = isContact
          ? 'باز کردن CRM <i class="fas fa-arrow-up-left" aria-hidden="true"></i>'
          : 'باز کردن CRM';
        const actionBlocks = getVisibleSpaceActionBlocks(card);
        const targets = actionBlocks.length
          ? actionBlocks
          : Array.from(
            card.querySelectorAll(
              '.agency-space-property-card__actions, .agency-space-contact-card__actions, .agency-space-card__actions',
            ),
          ).slice(0, 1);
        targets.forEach((actions) => {
          actions.appendChild(link.cloneNode(true));
        });
        if (isContact && !card.querySelector('.agency-space-contact-card__crm-badge:not(.agency-space-contact-card__crm-badge--foot)')) {
          const badgeHtml =
            '<i class="fas fa-circle-check" aria-hidden="true"></i> در CRM من';
          const statusCol = card.querySelector('.agency-space-contact-card__status-col');
          if (statusCol && isElementVisible(statusCol)) {
            const p = document.createElement('p');
            p.className = 'agency-space-contact-card__crm-badge';
            p.innerHTML = badgeHtml;
            const listActions = statusCol.querySelector('.agency-space-contact-card__actions--list');
            if (listActions) statusCol.insertBefore(p, listActions);
            else statusCol.appendChild(p);
          }
          const footMeta = card.querySelector('.agency-space-contact-card__foot-meta');
          const foot = card.querySelector('.agency-space-contact-card__foot');
          if (footMeta && foot && isElementVisible(foot) && !footMeta.querySelector('.agency-space-contact-card__crm-badge')) {
            const p = document.createElement('p');
            p.className = 'agency-space-contact-card__crm-badge agency-space-contact-card__crm-badge--foot';
            p.innerHTML = badgeHtml;
            footMeta.appendChild(p);
          }
        }
        const propertyCommerce = card.querySelector('.agency-space-property-card__commerce');
        if (propertyCommerce && !card.querySelector('.agency-space-property-card__crm-state')) {
          const p = document.createElement('p');
          p.className = 'agency-space-property-card__crm-state';
          p.innerHTML = '<i class="fas fa-circle-check" aria-hidden="true"></i> در CRM من';
          const propertyActions = propertyCommerce.querySelector('.agency-space-property-card__actions');
          if (propertyActions) propertyCommerce.insertBefore(p, propertyActions);
          else propertyCommerce.appendChild(p);
        } else if (!propertyCommerce) {
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
        const isContact = detailIsContact(detail);
        detail.querySelectorAll('.agency-space-detail__sticky-primary[data-space-copy], .agency-space-detail__sticky-primary.agency-space-btn--copy').forEach((el) => el.remove());
        const sticky = detail.querySelector('.agency-space-detail__sticky-inner');
        if (sticky && !sticky.querySelector('.agency-space-detail__sticky-primary[data-space-crm-link]')) {
          const stickyLink = document.createElement('a');
          stickyLink.href = targetUrl;
          stickyLink.className = 'crm-btn crm-btn-primary crm-btn-sm agency-space-detail__sticky-primary';
          stickyLink.setAttribute('data-space-crm-link', '');
          stickyLink.textContent = 'مشاهده در CRM';
          sticky.appendChild(stickyLink);
        }
        renderDetailCrmSuccess(detail, targetUrl, isContact);
      }
    }

    function copyButtonsForItem(itemId) {
      if (!itemId) return [];
      return Array.from(document.querySelectorAll(`[data-space-copy][data-item-id="${itemId}"]`));
    }

    function setCopyLoading(btn, on) {
      const itemId = btn?.dataset?.itemId;
      const targets = itemId ? copyButtonsForItem(itemId) : (btn ? [btn] : []);
      targets.forEach((target) => {
        if (on) {
          if (!target.dataset.spaceCopyLabel) target.dataset.spaceCopyLabel = target.innerHTML;
          target.classList.add('agency-space-btn--loading');
          target.setAttribute('aria-busy', 'true');
          target.disabled = true;
        } else {
          target.classList.remove('agency-space-btn--loading');
          target.removeAttribute('aria-busy');
          target.disabled = false;
          if (target.dataset.spaceCopyLabel) target.innerHTML = target.dataset.spaceCopyLabel;
        }
      });
    }

    document.querySelectorAll('[data-space-copy]').forEach((btn) => {
      btn.addEventListener('click', function () {
        const id = btn.dataset.itemId;
        if (!id || btn.disabled || btn.dataset.copying === '1') return;
        const detailRoot = btn.closest('.agency-space-detail');
        if (detailRoot && detailRoot.querySelector('[data-space-crm-link]')) return;
        const card = btn.closest('.agency-space-card');
        if (card && card.querySelector('[data-space-crm-link]')) return;
        copyButtonsForItem(id).forEach((b) => { b.dataset.copying = '1'; });
        setCopyLoading(btn, true);
        postJson(`/workspace/api/crm/agency/space/items/${id}/copy/`, {}).then((res) => {
          if (res.ok && res.data && res.data.target_url) {
            promoteCopyButton(btn, res.data.target_url);
            if (typeof window.showToast === 'function') {
              window.showToast('به CRM شما اضافه شد', 'success');
            }
          } else {
            copyButtonsForItem(id).forEach((b) => { b.dataset.copying = '0'; });
            setCopyLoading(btn, false);
            alert(res.error || 'خطا در کپی');
          }
        }).catch(() => {
          copyButtonsForItem(id).forEach((b) => { b.dataset.copying = '0'; });
          setCopyLoading(btn, false);
          alert('خطا در ارتباط');
        });
      });
    });

    const grid = document.querySelector('[data-space-grid]');
    const viewBtns = document.querySelectorAll('[data-space-view]');
    const viewKey = 'agency-space-view-mode-v2';
    function setView(mode) {
      if (!grid) return;
      grid.classList.toggle('is-list-view', mode === 'list');
      viewBtns.forEach((b) => {
        const on = b.dataset.spaceView === mode;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
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
      if (saved === 'list' || saved === 'grid') {
        setView(saved);
      } else {
        setView('grid');
      }
    } catch (e) {
      setView('grid');
    }

    const detail = document.querySelector('.agency-space-detail');
    if (detail) {
      const main = detail.querySelector('[data-space-gallery-main]');
      const lightboxImg = document.getElementById('agency-space-lightbox-img');
      const lightboxCounter = document.getElementById('agency-space-lightbox-counter');
      const lightboxFilmstrip = document.getElementById('agency-space-lightbox-filmstrip');
      const galleryModal = document.getElementById('modal-space-gallery');
      let galleryImages = [];
      const galleryScript = document.getElementById('space-property-gallery-images');
      if (galleryScript) {
        try {
          galleryImages = JSON.parse(galleryScript.textContent || '[]');
        } catch (e) {
          galleryImages = [];
        }
      }
      let galleryIndex = 0;
      let filmstripBuilt = false;

      const syncThumbActive = (index) => {
        detail.querySelectorAll('[data-space-gallery-thumb]').forEach((btn) => {
          const i = parseInt(btn.dataset.galleryIndex, 10);
          btn.classList.toggle('is-active', i === index);
        });
        if (lightboxFilmstrip) {
          lightboxFilmstrip.querySelectorAll('[data-gallery-film]').forEach((btn) => {
            const i = parseInt(btn.dataset.galleryFilm, 10);
            btn.classList.toggle('is-active', i === index);
          });
        }
      };

      const showGalleryIndex = (index, { openModal: shouldOpen } = {}) => {
        if (!galleryImages.length) return;
        galleryIndex = (index + galleryImages.length) % galleryImages.length;
        const src = galleryImages[galleryIndex];
        if (main) main.src = src;
        if (lightboxImg) lightboxImg.src = src;
        if (lightboxCounter) {
          lightboxCounter.textContent = `${galleryIndex + 1} / ${galleryImages.length}`;
        }
        syncThumbActive(galleryIndex);
        if (shouldOpen) openModal('modal-space-gallery');
      };

      const buildFilmstrip = () => {
        if (!lightboxFilmstrip || filmstripBuilt || galleryImages.length < 2) return;
        lightboxFilmstrip.innerHTML = '';
        galleryImages.forEach((src, i) => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'agency-space-lightbox__film';
          btn.dataset.galleryFilm = String(i);
          btn.setAttribute('aria-label', `تصویر ${i + 1}`);
          const img = document.createElement('img');
          img.src = src;
          img.alt = '';
          img.loading = 'lazy';
          btn.appendChild(img);
          btn.addEventListener('click', () => showGalleryIndex(i));
          lightboxFilmstrip.appendChild(btn);
        });
        filmstripBuilt = true;
      };

      const stepGallery = (delta) => {
        showGalleryIndex(galleryIndex + delta);
      };

      detail.querySelectorAll('[data-space-gallery-thumb]').forEach((btn) => {
        btn.addEventListener('click', function () {
          const idx = parseInt(btn.dataset.galleryIndex, 10);
          if (Number.isNaN(idx)) {
            showGalleryIndex(0, { openModal: true });
            return;
          }
          showGalleryIndex(idx, { openModal: true });
          buildFilmstrip();
        });
      });
      detail.querySelectorAll('[data-space-gallery-open]').forEach((btn) => {
        btn.addEventListener('click', function () {
          const idx = parseInt(btn.dataset.galleryIndex, 10);
          showGalleryIndex(Number.isNaN(idx) ? 0 : idx, { openModal: true });
          buildFilmstrip();
        });
      });

      let stageTouchX = 0;
      const galleryStage = detail.querySelector('.agency-space-prop-gallery__stage');
      if (galleryStage && galleryImages.length > 1) {
        galleryStage.addEventListener(
          'touchstart',
          (ev) => {
            stageTouchX = ev.changedTouches[0]?.screenX || 0;
          },
          { passive: true },
        );
        galleryStage.addEventListener(
          'touchend',
          (ev) => {
            const dx = (ev.changedTouches[0]?.screenX || 0) - stageTouchX;
            if (Math.abs(dx) < 48) return;
            showGalleryIndex(galleryIndex + (dx < 0 ? 1 : -1));
          },
          { passive: true },
        );
      }

      galleryModal?.querySelector('[data-gallery-prev]')?.addEventListener('click', () => stepGallery(-1));
      galleryModal?.querySelector('[data-gallery-next]')?.addEventListener('click', () => stepGallery(1));

      document.addEventListener('keydown', (ev) => {
        if (!galleryModal || galleryModal.hidden) return;
        if (ev.key === 'ArrowLeft') {
          ev.preventDefault();
          stepGallery(1);
        } else if (ev.key === 'ArrowRight') {
          ev.preventDefault();
          stepGallery(-1);
        } else if (ev.key === 'Escape') {
          const close = galleryModal.querySelector('[data-modal-close]');
          close?.click();
        }
      });

      let touchStartX = 0;
      lightboxImg?.addEventListener(
        'touchstart',
        (ev) => {
          touchStartX = ev.changedTouches[0]?.screenX || 0;
        },
        { passive: true },
      );
      lightboxImg?.addEventListener(
        'touchend',
        (ev) => {
          const dx = (ev.changedTouches[0]?.screenX || 0) - touchStartX;
          if (Math.abs(dx) < 40) return;
          stepGallery(dx < 0 ? 1 : -1);
        },
        { passive: true },
      );
    }

    function initAgencySpacePropertyMap() {
      const wrap = document.querySelector('[data-space-prop-map]');
      const mapEl = document.getElementById('agencySpacePropLocationMap');
      if (!wrap || !mapEl || typeof window.initListingDetailMap !== 'function' || !window.L) return;
      const lat = Number(wrap.dataset.lat);
      const lng = Number(wrap.dataset.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
      const title = wrap.dataset.title || '';
      const api = window.initListingDetailMap({
        uiPrefix: 'agencySpaceProp',
        mapId: 'agencySpacePropLocationMap',
        stageId: 'agencySpacePropMapStage',
        lat,
        lng,
        marker: { lat, lng, title },
        zoom: 16,
        editable: false,
        cartoBasemapKey: window.CartoBasemap?.getKey?.() || '',
      });
      if (api && typeof api.refresh === 'function') {
        requestAnimationFrame(() => {
          setTimeout(() => api.refresh(), 80);
        });
      }
    }

    initAgencySpacePropertyMap();

    document.querySelectorAll('[data-space-copy-phone]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const phone = (btn.dataset.spaceCopyPhone || '').trim();
        if (!phone) return;
        try {
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(phone);
          } else {
            const ta = document.createElement('textarea');
            ta.value = phone;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
          }
          btn.classList.add('is-copied');
          const icon = btn.querySelector('i');
          if (icon) {
            icon.classList.replace('fa-copy', 'fa-check');
            window.setTimeout(() => {
              btn.classList.remove('is-copied');
              icon.classList.replace('fa-check', 'fa-copy');
            }, 1600);
          }
        } catch (e) {
          /* ignore */
        }
      });
    });

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
