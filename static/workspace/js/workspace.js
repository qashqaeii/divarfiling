/* Divar Workspace v2 — Modal System */

function wsToPersianDigits(value) {
    return String(value || '').replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
}

function wsGregorianToJalali(gy, gm, gd) {
    const gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    let jy = gy <= 1600 ? 0 : 979;
    gy -= gy <= 1600 ? 621 : 1600;
    const gy2 = gm > 2 ? gy + 1 : gy;
    let days = (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100)
        + Math.floor((gy2 + 399) / 400) - 80 + gd + gdm[gm - 1];
    jy += 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    jy += Math.floor((days - 1) / 365);
    if (days > 365) days = (days - 1) % 365;
    const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
    return [jy, jm, jd];
}

function wsFormatJalaliToday() {
    const now = new Date();
    const [jy, jm, jd] = wsGregorianToJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
    return wsToPersianDigits(`${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`);
}

const WSModal = {
    active: null,

    open(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        if (this.active) this.close(this.active);
        modal.classList.add('is-open');
        document.body.classList.add('ws-modal-open');
        this.active = modal;
        const focusable = modal.querySelector('.ws-input, .ws-select, .ws-textarea, button, [tabindex]');
        if (focusable) setTimeout(() => focusable.focus(), 100);
    },

    close(modal) {
        const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
        if (!el) return;
        el.classList.remove('is-open');
        document.body.classList.remove('ws-modal-open');
        if (this.active === el) this.active = null;
    },

    closeAll() {
        document.querySelectorAll('.ws-modal.is-open').forEach(m => this.close(m));
    },

    confirm(title, message, actionUrl) {
        const titleEl = document.getElementById('confirmTitle');
        const msgEl = document.getElementById('confirmMessage');
        const actionEl = document.getElementById('confirmAction');
        const form = document.getElementById('confirmDeleteForm');
        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;
        if (actionEl && form) {
            actionEl.onclick = () => {
                form.action = actionUrl;
                form.submit();
            };
        }
        this.open('modal-confirm');
    },
};

function initWSGalleryLightbox() {
    const galleries = document.querySelectorAll('[data-ws-gallery]');
    if (!galleries.length) return;

    let lightbox = document.getElementById('wsGalleryLightbox');
    if (!lightbox) {
        lightbox = document.createElement('div');
        lightbox.id = 'wsGalleryLightbox';
        lightbox.className = 'ws-lightbox';
        lightbox.setAttribute('role', 'dialog');
        lightbox.setAttribute('aria-modal', 'true');
        lightbox.setAttribute('aria-hidden', 'true');
        lightbox.innerHTML = `
            <button type="button" class="ws-lightbox-backdrop" data-ws-lightbox-close aria-label="بستن"></button>
            <div class="ws-lightbox-panel">
                <div class="ws-lightbox-toolbar">
                    <p class="ws-lightbox-title" id="wsLightboxTitle"></p>
                    <div class="ws-lightbox-actions">
                        <span class="ws-lightbox-counter" id="wsLightboxCounter" aria-hidden="true"></span>
                        <button type="button" class="ws-lightbox-btn" id="wsLightboxPrev" aria-label="تصویر قبلی"><i class="fas fa-chevron-right"></i></button>
                        <button type="button" class="ws-lightbox-btn" id="wsLightboxNext" aria-label="تصویر بعدی"><i class="fas fa-chevron-left"></i></button>
                        <button type="button" class="ws-lightbox-btn" id="wsLightboxClose" aria-label="بستن"><i class="fas fa-xmark"></i></button>
                    </div>
                </div>
                <div class="ws-lightbox-stage">
                    <img class="ws-lightbox-img" id="wsLightboxImg" src="" alt="">
                </div>
            </div>`;
        document.body.appendChild(lightbox);
    }

    const imgEl = document.getElementById('wsLightboxImg');
    const titleEl = document.getElementById('wsLightboxTitle');
    const counterEl = document.getElementById('wsLightboxCounter');
    const prevBtn = document.getElementById('wsLightboxPrev');
    const nextBtn = document.getElementById('wsLightboxNext');
    const closeBtn = document.getElementById('wsLightboxClose');
    const backdrop = lightbox.querySelector('[data-ws-lightbox-close]');

    let items = [];
    let current = 0;
    let lastFocus = null;

    function render(index) {
        if (!items.length) return;
        current = (index + items.length) % items.length;
        const item = items[current];
        imgEl.src = item.src;
        imgEl.alt = item.alt;
        titleEl.textContent = item.alt;
        counterEl.textContent = items.length > 1 ? `${current + 1} / ${items.length}` : '';
        prevBtn.disabled = items.length <= 1;
        nextBtn.disabled = items.length <= 1;
        lightbox.setAttribute('aria-label', item.alt || 'بزرگ‌نمایی تصویر');
    }

    function open(index, galleryItems) {
        items = galleryItems;
        lastFocus = document.activeElement;
        render(index);
        lightbox.classList.add('is-open');
        lightbox.setAttribute('aria-hidden', 'false');
        document.body.classList.add('ws-lightbox-open');
        closeBtn.focus();
    }

    function close() {
        lightbox.classList.remove('is-open');
        lightbox.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('ws-lightbox-open');
        imgEl.removeAttribute('src');
        if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    }

    galleries.forEach(gallery => {
        const triggers = Array.from(gallery.querySelectorAll('[data-ws-lightbox]'));
        const galleryItems = triggers.map((btn, idx) => {
            const src = btn.getAttribute('data-ws-lightbox') || '';
            const thumb = btn.querySelector('img');
            const alt = thumb?.getAttribute('alt') || `تصویر ${idx + 1}`;
            return { src, alt };
        }).filter(item => item.src);

        triggers.forEach((btn, index) => {
            btn.addEventListener('click', () => open(index, galleryItems));
        });
    });

    prevBtn.addEventListener('click', () => render(current - 1));
    nextBtn.addEventListener('click', () => render(current + 1));
    closeBtn.addEventListener('click', close);
    backdrop.addEventListener('click', close);

    document.addEventListener('keydown', e => {
        if (!lightbox.classList.contains('is-open')) return;
        if (e.key === 'Escape') {
            e.preventDefault();
            close();
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            render(current + 1);
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            render(current - 1);
        }
    });

    let touchStartX = 0;
    let touchStartY = 0;
    const stage = lightbox.querySelector('.ws-lightbox-stage');
    if (stage) {
        stage.addEventListener('touchstart', e => {
            if (!lightbox.classList.contains('is-open')) return;
            touchStartX = e.changedTouches[0].clientX;
            touchStartY = e.changedTouches[0].clientY;
        }, { passive: true });
        stage.addEventListener('touchend', e => {
            if (!lightbox.classList.contains('is-open')) return;
            const dx = e.changedTouches[0].clientX - touchStartX;
            const dy = e.changedTouches[0].clientY - touchStartY;
            if (Math.abs(dx) < 44 || Math.abs(dx) < Math.abs(dy)) return;
            render(dx < 0 ? current + 1 : current - 1);
        }, { passive: true });
    }
}

function initWSGalleryHeroTriggers() {
    document.querySelectorAll('[data-ws-gallery-hero]').forEach(hero => {
        if (hero.dataset.wsGalleryHeroBound === '1') return;
        hero.dataset.wsGalleryHeroBound = '1';
        hero.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const root = document.querySelector('.ws-ld-mobile-gallery[data-ws-gallery]')
                || hero.closest('[data-ws-gallery]')
                || document.querySelector('[data-ws-gallery]');
            if (!root) return;
            const triggers = Array.from(root.querySelectorAll('[data-ws-lightbox]')).filter(btn => {
                return (btn.getAttribute('data-ws-lightbox') || '').trim();
            });
            if (!triggers.length) return;
            const heroSrc = (hero.getAttribute('data-ws-lightbox') || '').trim();
            const match = heroSrc ? triggers.findIndex(btn => btn.getAttribute('data-ws-lightbox') === heroSrc) : 0;
            (triggers[match >= 0 ? match : 0]).click();
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // Sidebar mobile
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('wsSidebar');

    function setSidebarOpen(open) {
        if (!sidebar) return;
        sidebar.classList.toggle('open', open);
        document.body.classList.toggle('ws-sidebar-open', open);
        const backdrop = document.getElementById('wsShellBackdrop');
        if (backdrop) {
            backdrop.hidden = !open;
            backdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
        }
        if (toggle) {
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            toggle.setAttribute('aria-label', open ? 'بستن منو' : 'باز کردن منو');
            const icon = toggle.querySelector('i');
            if (icon) icon.className = open ? 'fas fa-times' : 'fas fa-bars';
        }
    }

    const bottomMore = document.querySelector('[data-ws-bottom-more]');
    const bottomNav = document.getElementById('wsBottomNav');
    const shellBackdrop = document.getElementById('wsShellBackdrop');

    if (sidebar) {
        if (toggle) {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                setSidebarOpen(!sidebar.classList.contains('open'));
            });
        }

        bottomMore?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            setSidebarOpen(!sidebar.classList.contains('open'));
        });

        shellBackdrop?.addEventListener('click', () => setSidebarOpen(false));

        document.addEventListener('click', (e) => {
            if (!sidebar.classList.contains('open')) return;
            if (
                sidebar.contains(e.target)
                || toggle?.contains(e.target)
                || bottomMore?.contains(e.target)
                || bottomNav?.contains(e.target)
            ) return;
            setSidebarOpen(false);
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && sidebar.classList.contains('open')) {
                setSidebarOpen(false);
            }
        });
    }

    // Modal triggers
    document.querySelectorAll('[data-modal-open]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            WSModal.open(btn.dataset.modalOpen);
        });
    });

    // Modal close
    document.querySelectorAll('[data-modal-close]').forEach(el => {
        el.addEventListener('click', () => {
            const modal = el.closest('.ws-modal');
            if (modal) WSModal.close(modal);
        });
    });

    // ESC close
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') WSModal.closeAll();
    });

    // Confirm delete buttons
    document.querySelectorAll('[data-confirm]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            WSModal.confirm(
                btn.dataset.confirmTitle || 'تأیید حذف',
                btn.dataset.confirmMessage || 'آیا مطمئن هستید؟',
                btn.dataset.confirmUrl || btn.href
            );
        });
    });

    // Auto-open from server (CRM drawers are handled in crm.js)
    const openId = document.body.dataset.openModal;
    if (openId) {
        const openEl = document.getElementById(openId);
        if (!openEl || !openEl.classList.contains('crm-drawer')) {
            WSModal.open(openId);
        }
    }

    // Auto-dismiss toasts — handled by mk-notices.js

    // Upload zone
    initUploadZone();
    initSettingsModal();

    // Tabs
    document.querySelectorAll('[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            const parent = btn.closest('.crm-prop-main, .crm-detail-main, .ws-card, .ws-modal-body, .ws-content');
            if (!parent) return;
            parent.querySelectorAll('[data-tab]').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            parent.querySelectorAll('[data-panel]').forEach(p => p.hidden = true);
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            const panel = parent.querySelector(`[data-panel="${tab}"]`);
            if (panel) panel.hidden = false;
        });
    });

    document.querySelectorAll('[data-tab-jump]').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tabJump;
            const shell = btn.closest('.crm-prop-detail-v2') || document.querySelector('.crm-prop-main');
            const tabBtn = shell?.querySelector(`[data-tab="${tab}"]`);
            tabBtn?.click();
        });
    });

    // Copy
    document.querySelectorAll('[data-copy]').forEach(btn => {
        btn.addEventListener('click', () => {
            navigator.clipboard.writeText(btn.dataset.copy).then(() => {
                const orig = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(() => { btn.innerHTML = orig; }, 2000);
            });
        });
    });

    // Charts (deferred — analyze page loads Chart.js in extra_js after this file)
    if (typeof window.wsCharts !== 'undefined' && window.Chart) {
        initCharts(window.wsCharts);
    }

    initConfidenceRings();
    initL2Tabs();

    initThemeToggle();
    initClock();
    initGlobalSearchShortcut();
    document.querySelectorAll('[data-mk-table]').forEach(initMkDataTable);
    initDatasetBulkSelect();
    initFormattedNumericInputs();
    initPublicShareForms();
    initWSGalleryLightbox();
    initWSGalleryHeroTriggers();
});

function getCsrfToken() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el && el.value) return el.value;
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

function buildDefaultShareMessage(title, url, template) {
    const safeTitle = (title || 'ملک').trim() || 'ملک';
    const safeUrl = (url || '').trim();
    const tpl = (template || '').trim() || 'سلام،\nجزئیات «{title}» را در این لینک ببینید:\n{url}\nبا تشکر مشاور شما';
    return tpl
        .split('{title}').join(safeTitle)
        .split('{TITLE}').join(safeTitle)
        .split('{url}').join(safeUrl)
        .split('{URL}').join(safeUrl);
}

function getDefaultShareTemplate(template) {
    return (template || '').trim() || 'سلام،\nجزئیات «{title}» را در این لینک ببینید:\n{url}\nبا تشکر مشاور شما';
}

function messageToShareTemplate(text, title, url) {
    let out = (text || '').trim();
    const safeUrl = (url || '').trim();
    const safeTitle = (title || '').trim();
    if (safeUrl && out.includes(safeUrl)) {
        out = out.split(safeUrl).join('{url}');
    }
    if (safeTitle && out.includes(safeTitle)) {
        out = out.split(safeTitle).join('{title}');
    }
    return out || getDefaultShareTemplate();
}

function syncShareMessageUrl(form, nextUrl) {
    if (!nextUrl) return;
    const root = form.querySelector('[data-share-msg-root]');
    const ta = form.querySelector('[data-share-message]');
    if (!root || !ta) return;
    root.dataset.shareUrl = nextUrl;
    if (!ta.value.trim()) {
        ta.value = getDefaultShareTemplate(
            root.dataset.shareTemplate || form.querySelector('[data-share-msg-template]')?.value,
        );
    }
    ta.dispatchEvent(new Event('input', { bubbles: true }));
}

function initShareModalTabs(form) {
    const tabs = form.querySelector('[data-share-tabs]');
    if (!tabs || tabs.dataset.bound === '1') return;
    tabs.dataset.bound = '1';
    tabs.querySelectorAll('[data-share-tab]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.shareTab;
            tabs.querySelectorAll('[data-share-tab]').forEach((b) => {
                const on = b === btn;
                b.classList.toggle('is-active', on);
                b.setAttribute('aria-selected', on ? 'true' : 'false');
            });
            form.querySelectorAll('[data-share-pane]').forEach((pane) => {
                const on = pane.dataset.sharePane === key;
                pane.classList.toggle('is-active', on);
                pane.hidden = !on;
            });
        });
    });
}

function initWelcomeRichEditors(form) {
    const rte = form.querySelector('[data-welcome-rte]');
    if (!rte || rte.dataset.bound === '1') return;
    rte.dataset.bound = '1';
    const editor = rte.querySelector('[data-welcome-editor]');
    const hidden = form.querySelector('[data-welcome-input]');
    if (!editor || !hidden) return;

    const syncHidden = () => {
        const html = (editor.innerHTML || '').trim();
        const plain = (editor.innerText || '').trim();
        hidden.value = plain ? html : '';
        editor.classList.toggle('is-empty', !plain);
    };

    editor.classList.toggle('is-empty', !(editor.innerText || '').trim());

    rte.querySelectorAll('[data-rte-cmd]').forEach((btn) => {
        btn.addEventListener('mousedown', (e) => e.preventDefault());
        btn.addEventListener('click', () => {
            const cmd = btn.dataset.rteCmd;
            editor.focus();
            if (cmd === 'createLink') {
                const url = window.prompt('آدرس لینک را وارد کنید:', 'https://');
                if (url) document.execCommand('createLink', false, url);
            } else {
                document.execCommand(cmd, false, null);
            }
            syncHidden();
        });
    });

    editor.addEventListener('input', syncHidden);
    editor.addEventListener('blur', syncHidden);
    form.addEventListener('submit', syncHidden);
}

function initPublicShareMessageEditors() {
    document.querySelectorAll('[data-share-msg-root]').forEach((root) => {
        if (root.dataset.shareMsgBound === '1') return;
        root.dataset.shareMsgBound = '1';
        const ta = root.querySelector('[data-share-message]');
        if (!ta) return;
        const form = root.closest('form');
        const preview = root.querySelector('[data-share-msg-preview]');

        const escapeHtml = (s) => String(s || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');

        const linkifyPreview = (text) => {
            const escaped = escapeHtml(text);
            return escaped
                .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener" dir="ltr">$1</a>')
                .replace(/\n/g, '<br>');
        };

        const getRenderedMessage = () => buildDefaultShareMessage(
            root.dataset.listingTitle,
            root.dataset.shareUrl,
            ta.value || getDefaultShareTemplate(root.dataset.shareTemplate),
        );

        const syncPreview = () => {
            if (!preview) return;
            const tpl = (ta.value || '').trim();
            if (!tpl) {
                preview.innerHTML = '<span class="mk-share-live-preview-empty">متن پیام را بنویسید…</span>';
                return;
            }
            preview.innerHTML = linkifyPreview(getRenderedMessage());
        };

        syncPreview();
        ta.addEventListener('input', syncPreview);
        ta.addEventListener('change', syncPreview);

        const setBtnLabel = (btn, label, restoreMs = 1600) => {
            if (!btn) return;
            const span = btn.querySelector('span');
            if (!span) return;
            const prev = span.textContent;
            span.textContent = label;
            window.setTimeout(() => {
                span.textContent = prev;
            }, restoreMs);
        };

        const copyText = async (text) => {
            if (!text) return false;
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(text);
                    return true;
                }
            } catch (_) { /* fallback below */ }
            try {
                const tmp = document.createElement('textarea');
                tmp.value = text;
                tmp.setAttribute('readonly', '');
                tmp.style.position = 'fixed';
                tmp.style.opacity = '0';
                document.body.appendChild(tmp);
                tmp.select();
                const ok = document.execCommand('copy');
                document.body.removeChild(tmp);
                return ok;
            } catch (_) {
                return false;
            }
        };

        root.querySelector('[data-share-msg-copy]')?.addEventListener('click', async (e) => {
            const btn = e.currentTarget;
            const text = getRenderedMessage().trim();
            if (!text) {
                if (typeof window.showWsToast === 'function') {
                    window.showWsToast('متن اشتراک خالی است.', 'warning');
                }
                return;
            }
            const ok = await copyText(text);
            if (ok) {
                setBtnLabel(btn, 'کپی شد');
                if (typeof window.showWsToast === 'function') {
                    window.showWsToast('متن نهایی (با عنوان و لینک) کپی شد.', 'success');
                }
            } else if (typeof window.showWsToast === 'function') {
                window.showWsToast('کپی انجام نشد؛ متن را دستی انتخاب کنید.', 'error');
            }
        });

        const openShareChannel = async (btn) => {
            const mode = (btn.getAttribute('data-send-mode') || '').trim();
            const href = (btn.getAttribute('data-send-href') || '').trim();
            const label = (btn.getAttribute('data-send-label') || 'پیام‌رسان').trim();
            const text = getRenderedMessage().trim();
            const url = (root.dataset.shareUrl || '').trim();
            if (!text && mode !== 'telegram') {
                if (typeof window.showWsToast === 'function') {
                    window.showWsToast('ابتدا متن اشتراک را بنویسید.', 'warning');
                }
                return;
            }
            if (mode === 'whatsapp') {
                window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
                return;
            }
            if (mode === 'telegram') {
                if (!text && !url) {
                    if (typeof window.showWsToast === 'function') {
                        window.showWsToast('ابتدا متن اشتراک را بنویسید.', 'warning');
                    }
                    return;
                }
                const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text || url)}`;
                window.open(tgUrl, '_blank', 'noopener');
                return;
            }
            // copy_open: کپی متن و باز کردن پروفایل/چت ذخیره‌شده
            if (text) {
                const ok = await copyText(text);
                if (ok && typeof window.showWsToast === 'function') {
                    window.showWsToast(`متن کپی شد — در ${label} جای‌گذاری کنید.`, 'success');
                }
            }
            if (href) {
                window.open(href, '_blank', 'noopener');
            } else if (typeof window.showWsToast === 'function') {
                window.showWsToast(`لینک ${label} ذخیره نشده است.`, 'warning');
            }
        };

        root.querySelectorAll('[data-share-msg-send]').forEach((btn) => {
            btn.addEventListener('click', () => {
                openShareChannel(btn);
            });
        });

        // سازگاری با دکمه‌های قدیمی
        root.querySelector('[data-share-msg-wa]')?.addEventListener('click', () => {
            window.open(`https://wa.me/?text=${encodeURIComponent(getRenderedMessage().trim())}`, '_blank', 'noopener');
        });
        root.querySelector('[data-share-msg-tg]')?.addEventListener('click', () => {
            const text = getRenderedMessage().trim();
            const url = (root.dataset.shareUrl || '').trim();
            window.open(
                `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text || url)}`,
                '_blank',
                'noopener',
            );
        });

        root.querySelector('[data-share-msg-reset]')?.addEventListener('click', () => {
            const tpl = getDefaultShareTemplate(
                root.dataset.shareTemplate
                || form?.querySelector('[data-share-msg-template]')?.value
                || '',
            );
            ta.value = tpl;
            syncPreview();
            ta.focus();
            if (typeof window.showWsToast === 'function') {
                window.showWsToast('قالب پیش‌فرض بازگردانی شد.', 'info');
            }
        });
    });
}

function prepareShareFormSubmit(form) {
    const root = form.querySelector('[data-share-msg-root]');
    const ta = form.querySelector('[data-share-message]');
    const tplInput = form.querySelector('[data-share-msg-template]');
    const saveDefaultMsg = form.querySelector('[data-save-default-msg], [name="save_as_default_share_message"]');
    if (root && ta && tplInput && saveDefaultMsg && saveDefaultMsg.checked) {
        // textarea خودش قالب است ({title}/{url})؛ اگر کاربر مقادیر واقعی نوشته بود برمی‌گردانیم
        tplInput.value = messageToShareTemplate(
            ta.value,
            root.dataset.listingTitle,
            root.dataset.shareUrl,
        );
    } else if (ta && tplInput) {
        tplInput.value = (ta.value || '').trim() || getDefaultShareTemplate(tplInput.value);
    }
    const editor = form.querySelector('[data-welcome-editor]');
    const hidden = form.querySelector('[data-welcome-input]');
    if (editor && hidden) {
        const plain = (editor.innerText || '').trim();
        hidden.value = plain ? (editor.innerHTML || '').trim() : '';
    }
}

function initApproxRadiusToggle(form) {
    const toggle = form.querySelector('[data-approx-toggle]');
    const radiusWrap = form.querySelector('[data-approx-radius]');
    if (!toggle || !radiusWrap) return;
    const sync = () => {
        radiusWrap.hidden = !toggle.checked;
        const input = radiusWrap.querySelector('input[name="approximate_location_radius_m"]');
        if (input) input.disabled = !toggle.checked;
    };
    toggle.addEventListener('change', sync);
    sync();
}

function initNearbyPoisShareToggle(form) {
    const wrap = form.querySelector('[data-nearby-pois-toggle-wrap]');
    const toggle = form.querySelector('[data-nearby-pois-toggle]');
    if (!wrap || !toggle) return;

    const hasCoords = wrap.dataset.hasCoords === '1';
    const hasData = wrap.dataset.hasData === '1';

    const notify = (msg) => {
        if (typeof window.showWsToast === 'function') {
            window.showWsToast(msg, 'warning');
        } else if (typeof window.showToast === 'function') {
            window.showToast(msg, 'error');
        } else {
            window.alert(msg);
        }
    };

    toggle.addEventListener('change', () => {
        if (!toggle.checked) return;
        if (!hasCoords) {
            toggle.checked = false;
            notify('برای نمایش امکانات و دسترسی‌ها، ابتدا موقعیت ملک را روی نقشه ثبت کنید.');
            return;
        }
        if (!hasData) {
            toggle.checked = false;
            notify('ابتدا در جزئیات فایل، دکمه «محاسبه» امکانات و دسترسی‌ها را بزنید.');
        }
    });

    form.addEventListener('submit', (e) => {
        if (!toggle.checked) return;
        if (!hasCoords) {
            e.preventDefault();
            e.stopImmediatePropagation();
            notify('برای نمایش امکانات و دسترسی‌ها، ابتدا موقعیت ملک را روی نقشه ثبت کنید.');
            return;
        }
        if (!hasData) {
            e.preventDefault();
            e.stopImmediatePropagation();
            notify('ابتدا در جزئیات فایل، دکمه «محاسبه» امکانات و دسترسی‌ها را بزنید.');
        }
    }, true);
}

function initPublicShareForms() {
    initPublicShareMessageEditors();
    document.querySelectorAll('.mk-share-form').forEach((form) => {
        if (form.dataset.shareAjaxBound === '1') return;
        form.dataset.shareAjaxBound = '1';
        initShareModalTabs(form);
        initWelcomeRichEditors(form);
        initShareProfileImagePreviews(form);
        initApproxRadiusToggle(form);
        initNearbyPoisShareToggle(form);
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            prepareShareFormSubmit(form);
            const submitBtn = form.querySelector('[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;
            try {
                const body = new FormData(form);
                const res = await fetch(form.action, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body,
                    credentials: 'same-origin',
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.ok) {
                    window.alert(data.error || data.message || 'ذخیره تنظیمات انجام نشد.');
                    return;
                }
                const urlInput = form.querySelector('.mk-share-link-input');
                if (urlInput && data.share_url) urlInput.value = data.share_url;
                form.querySelectorAll('[data-copy]').forEach((btn) => {
                    if (data.share_url) btn.dataset.copy = data.share_url;
                });
                if (data.share_url) syncShareMessageUrl(form, data.share_url);
                const modal = form.closest('.ws-modal');
                if (typeof WSModal !== 'undefined' && modal) WSModal.close(modal);
                if (typeof window.showWsToast === 'function') {
                    window.showWsToast(data.message || 'تنظیمات اشتراک ذخیره شد.', 'success');
                } else {
                    window.alert(data.message || 'تنظیمات اشتراک ذخیره شد.');
                }
            } catch (err) {
                window.alert('خطای شبکه — دوباره تلاش کنید.');
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        });
    });
}

function initShareProfileImagePreviews(form) {
    form.querySelectorAll('input[type="file"][data-image-preview]').forEach((input) => {
        if (input.dataset.previewBound === '1') return;
        input.dataset.previewBound = '1';
        input.addEventListener('change', () => {
            const file = input.files && input.files[0];
            if (!file) return;
            const row = input.closest('.mk-share-upload-row');
            const preview = row && row.querySelector('[data-photo-preview], [data-card-preview], .mk-share-upload-preview');
            if (!preview) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
                let img = preview.querySelector('img');
                if (!img) {
                    preview.innerHTML = '';
                    img = document.createElement('img');
                    img.width = 72;
                    img.height = 72;
                    img.alt = '';
                    preview.appendChild(img);
                }
                img.src = ev.target.result;
            };
            reader.readAsDataURL(file);
        });
    });
}

function initDatasetBulkSelect() {
    const selectAll = document.getElementById('dsSelectAll');
    const bulkBar = document.getElementById('dsBulkBar');
    const bulkCount = document.getElementById('dsBulkCount');
    const bulkClear = document.getElementById('dsBulkClear');
    const bulkView = document.getElementById('dsBulkView');
    const bulkDelete = document.getElementById('dsBulkDelete');
    const bulkForm = document.getElementById('dsBulkDeleteForm');
    const bulkIds = document.getElementById('dsBulkDeleteIds');
    const layoutRoot = document.querySelector('.mk-ds-layout');

    function isVisible(el) {
        return !!(el && el.offsetParent !== null);
    }

    function activeLayoutSection() {
        if (!layoutRoot) return document;
        const grid = layoutRoot.querySelector('.mk-ds-layout-grid');
        const table = layoutRoot.querySelector('.mk-ds-layout-table');
        if (isVisible(grid)) return grid;
        if (isVisible(table)) return table;
        return layoutRoot;
    }

    function getChecks() {
        const scope = activeLayoutSection();
        return [...scope.querySelectorAll('.mk-ds-check')];
    }

    if (!document.querySelector('.mk-ds-check')) return;

    function selected() {
        return getChecks().filter(c => c.checked);
    }

    function syncRowHighlight() {
        getChecks().forEach(c => {
            const row = c.closest('tr[data-id], .mk-ds-card[data-id]');
            if (row) row.classList.toggle('is-selected', c.checked);
        });
    }

    function updateBulk() {
        const checks = getChecks();
        const picked = selected();
        const n = picked.length;
        if (bulkBar) {
            bulkBar.hidden = n === 0;
            bulkBar.classList.toggle('is-visible', n > 0);
        }
        if (bulkCount) bulkCount.textContent = n;
        if (selectAll && isVisible(selectAll.closest('.mk-ds-layout-table'))) {
            selectAll.checked = n > 0 && n === checks.length;
            selectAll.indeterminate = n > 0 && n < checks.length;
        } else if (selectAll) {
            selectAll.checked = false;
            selectAll.indeterminate = false;
        }
        syncRowHighlight();
    }

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            getChecks().forEach(c => { c.checked = selectAll.checked; });
            updateBulk();
        });
    }
    document.querySelectorAll('.mk-ds-check').forEach(c => c.addEventListener('change', updateBulk));

    if (bulkClear) {
        bulkClear.addEventListener('click', () => {
            document.querySelectorAll('.mk-ds-check').forEach(c => { c.checked = false; });
            if (selectAll) selectAll.checked = false;
            updateBulk();
        });
    }

    if (bulkView) {
        bulkView.addEventListener('click', () => {
            const ids = selected().map(c => c.value);
            if (!ids.length) return;
            const base = bulkView.dataset.url || '/workspace/listings/';
            const params = new URLSearchParams();
            params.set('dataset_ids', ids.join(','));
            window.location.href = base + (base.includes('?') ? '&' : '?') + params.toString();
        });
    }

    if (bulkDelete && bulkForm && bulkIds) {
        bulkDelete.addEventListener('click', () => {
            const ids = selected().map(c => c.value);
            if (!ids.length) return;
            WSModal.confirm(
                'حذف دسته‌جمعی',
                `${ids.length} فایل انتخاب‌شده حذف شود؟ این عمل قابل بازگشت نیست.`,
                '',
            );
            const actionEl = document.getElementById('confirmAction');
            if (actionEl) {
                actionEl.onclick = () => {
                    bulkIds.innerHTML = '';
                    ids.forEach(id => {
                        const inp = document.createElement('input');
                        inp.type = 'hidden';
                        inp.name = 'ids';
                        inp.value = id;
                        bulkIds.appendChild(inp);
                    });
                    bulkForm.submit();
                    WSModal.close('modal-confirm');
                };
            }
        });
    }
}

function initMkDataTable(table) {
    const tbody = table.querySelector('tbody');
    const headers = table.querySelectorAll('th[data-sort]');
    if (!tbody || !headers.length) return;

    let sortCol = null;
    let sortDir = 1;

    headers.forEach(th => {
        th.classList.add('mk-sortable');
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            const type = th.dataset.sortType || 'string';
            if (sortCol === col) sortDir *= -1;
            else { sortCol = col; sortDir = 1; }

            headers.forEach(h => h.classList.remove('mk-sorted-asc', 'mk-sorted-desc'));
            th.classList.add(sortDir === 1 ? 'mk-sorted-asc' : 'mk-sorted-desc');

            const idx = Array.from(th.parentNode.children).indexOf(th);
            const rows = Array.from(tbody.querySelectorAll('tr'));

            rows.sort((a, b) => {
                const aCell = a.children[idx];
                const bCell = b.children[idx];
                let av = aCell?.dataset.sortValue ?? aCell?.textContent.trim();
                let bv = bCell?.dataset.sortValue ?? bCell?.textContent.trim();

                if (type === 'number' || type === 'date') {
                    av = parseFloat(av) || 0;
                    bv = parseFloat(bv) || 0;
                    return (av - bv) * sortDir;
                }
                return String(av).localeCompare(String(bv), 'fa') * sortDir;
            });

            rows.forEach(r => tbody.appendChild(r));
        });
    });
}

function themeIconClass(theme) {
    if (theme === 'dark') return 'fas fa-moon';
    if (theme === 'cheerful') return 'fas fa-face-smile';
    return 'fas fa-sun';
}

function initThemeToggle() {
    const btn = document.getElementById('themeToggle');
    const html = document.documentElement;
    if (!btn) return;
    const themeOrder = ['light', 'cheerful', 'dark'];
    btn.addEventListener('click', () => {
        const current = html.dataset.theme || 'light';
        const idx = themeOrder.indexOf(current);
        const next = themeOrder[(idx + 1) % themeOrder.length];
        html.dataset.theme = next;
        localStorage.setItem('ws-theme', next);
        const icon = btn.querySelector('i');
        if (icon) icon.className = themeIconClass(next);
    });
    const saved = localStorage.getItem('ws-theme');
    if (themeOrder.includes(saved)) {
        html.dataset.theme = saved;
    } else {
        html.dataset.theme = 'light';
        localStorage.setItem('ws-theme', 'light');
    }
    const icon = btn.querySelector('i');
    if (icon) icon.className = themeIconClass(html.dataset.theme);
}

function initClock() {
    const clock = document.getElementById('wsClock');
    const date = document.getElementById('wsDate');
    if (!clock) return;
    const days = ['یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه'];
    const months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
    function tick() {
        const now = new Date();
        const h = now.getHours().toString().padStart(2, '0');
        const m = now.getMinutes().toString().padStart(2, '0');
        const s = now.getSeconds().toString().padStart(2, '0');
        const ap = now.getHours() < 12 ? 'صبح' : 'عصر';
        clock.textContent = `${h}:${m}:${s} ${ap}`;
        if (date) {
            date.textContent = `${days[now.getDay()]}، ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear() + 621}`;
        }
    }
    tick();
    setInterval(tick, 1000);
}

function initGlobalSearchShortcut() {
    const input = document.getElementById('wsSearchInput') || document.getElementById('crmSearchInput');
    document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            if (input) input.focus();
        }
    });
    const wsInput = document.getElementById('wsSearchInput');
    if (wsInput) {
        wsInput.addEventListener('focus', () => {
            const crm = document.getElementById('crmSearchInput');
            if (crm) crm.focus();
        });
    }
}

const IMPORTABLE_EXT = new Set(['.xlsx', '.xls', '.csv', '.json']);
const SKIP_EXT = new Set(['.pdf', '.html', '.htm', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.zip', '.db']);
const SKIP_NAMES = new Set(['error_report.txt', 'temp_map.html', 'thumbnails.json', '.ds_store']);
const TOKEN_DIR_RE = /^[a-zA-Z0-9]{6,12}$/;

function isImportablePath(relPath) {
    const path = (relPath || '').replace(/\\/g, '/');
    const base = path.split('/').pop() || '';
    if (!base || base.startsWith('.') || base.startsWith('~$') || SKIP_NAMES.has(base.toLowerCase())) return false;
    const dot = base.lastIndexOf('.');
    const ext = dot >= 0 ? base.slice(dot).toLowerCase() : '';
    if (!ext || SKIP_EXT.has(ext)) return false;
    return IMPORTABLE_EXT.has(ext);
}

function stripOutputParts(parts) {
    const idx = parts.findIndex(p => p.toLowerCase() === 'output');
    return idx >= 0 ? parts.slice(idx + 1) : parts;
}

function _looksLikeTxDir(part) {
    const slug = (part || '').replace(/_/g, ' ');
    if (/اجاره|رهن/.test(slug)) return true;
    if (/فروش/.test(slug)) return true;
    return false;
}

function parseLocationDirs(dirs) {
    const norm = s => (s || '').trim().replace(/_/g, ' ');
    if (!dirs.length) return { province: '', city: '', district: '' };
    if (dirs.length === 1) return { province: '', city: norm(dirs[0]), district: '' };
    if (dirs.length === 2) return { province: norm(dirs[0]), city: norm(dirs[1]), district: '' };
    return { province: norm(dirs[0]), city: norm(dirs[1]), district: norm(dirs[2]) };
}

function parseOutputPath(relPath) {
    let parts = (relPath || '').replace(/\\/g, '/').split('/').filter(p => p && p !== '.');
    if (!parts.length) return null;
    parts = stripOutputParts(parts);
    const filename = parts.pop();
    let dirs = parts.slice();
    while (dirs.length && TOKEN_DIR_RE.test(dirs[dirs.length - 1])) dirs.pop();
    let loc = parseLocationDirs(dirs);
    if (dirs.length === 2 && _looksLikeTxDir(dirs[1]) && !_looksLikeTxDir(dirs[0])) {
        loc = { province: '', city: (dirs[0] || '').trim().replace(/_/g, ' '), district: '' };
    }
    const rel = stripOutputParts((relPath || '').replace(/\\/g, '/').split('/').filter(p => p && p !== '.')).join('/');
    return { ...loc, filename, relative_path: rel };
}

function groupFilesByLocation(files) {
    const tree = {};
    let importable = 0;
    files.forEach(file => {
        const rel = file.webkitRelativePath || file.name;
        if (!isImportablePath(rel)) return;
        importable += 1;
        const info = parseOutputPath(rel) || {};
        const prov = info.province || 'سایر';
        const city = info.city || '—';
        if (!tree[prov]) tree[prov] = {};
        if (!tree[prov][city]) tree[prov][city] = [];
        tree[prov][city].push({ name: info.filename || file.name, path: rel });
    });
    return { tree, importable, total: files.length };
}

function renderFolderPreview(tree) {
    const provinces = Object.keys(tree).sort((a, b) => {
        if (a === 'سایر') return 1;
        if (b === 'سایر') return -1;
        return a.localeCompare(b, 'fa');
    });
    return provinces.map(prov => {
        const cities = Object.keys(tree[prov]).sort((a, b) => {
            if (a === '—') return 1;
            if (b === '—') return -1;
            return a.localeCompare(b, 'fa');
        });
        const cityHtml = cities.map(city => {
            const files = tree[prov][city].sort((a, b) => a.name.localeCompare(b.name, 'fa'));
            const items = files.map(f =>
                `<li class="mk-folder-file"><i class="fas fa-file-excel" aria-hidden="true"></i><span>${f.name}</span></li>`
            ).join('');
            return `<div class="mk-folder-city"><div class="mk-folder-city-name">${city}</div><ul class="mk-folder-file-list">${items}</ul></div>`;
        }).join('');
        return `<section class="mk-folder-province"><div class="mk-folder-province-name"><i class="fas fa-map-marker-alt"></i> ${prov}</div>${cityHtml}</section>`;
    }).join('');
}

function initSettingsModal() {
    const form = document.getElementById('wsSettingsForm');
    if (!form) return;

    const preview = document.getElementById('wsSettingsPreview');
    const themeCards = form.querySelectorAll('.ws-settings-theme-card');
    const themeInputs = form.querySelectorAll('.ws-settings-theme-input');
    const fontRange = document.getElementById('wsFontScaleRange');
    const fontHidden = document.getElementById('id_font_scale');
    const fontOut = document.getElementById('wsFontScaleOut');
    const kmeansRange = document.getElementById('wsKmeansRange');
    const kmeansHidden = document.getElementById('id_map_kmeans');
    const kmeansOut = document.getElementById('wsKmeansOut');
    const logoZone = document.getElementById('wsLogoZone');
    const logoInput = document.getElementById('id_agency_logo');
    const logoFileName = document.getElementById('wsLogoFileName');
    const logoCurrent = document.getElementById('wsLogoCurrent');
    const html = document.documentElement;

    function syncThemeCards(value) {
        themeCards.forEach(card => {
            card.classList.toggle('is-active', card.dataset.theme === value);
        });
        if (preview) preview.dataset.theme = value;
    }

    themeInputs.forEach(input => {
        input.addEventListener('change', () => {
            if (!input.checked) return;
            syncThemeCards(input.value);
            html.dataset.theme = input.value;
            const toggleBtn = document.getElementById('themeToggle');
            const toggleIcon = toggleBtn?.querySelector('i');
            if (toggleIcon) toggleIcon.className = themeIconClass(input.value);
        });
    });

    if (fontRange && fontHidden) {
        const syncFont = () => {
            const val = parseFloat(fontRange.value);
            fontHidden.value = val.toFixed(1);
            if (fontOut) fontOut.textContent = val.toFixed(1);
            html.style.setProperty('--ws-font-scale', val);
        };
        fontRange.addEventListener('input', syncFont);
        syncFont();
    }

    if (kmeansRange && kmeansHidden) {
        const syncKmeans = () => {
            const val = parseInt(kmeansRange.value, 10);
            kmeansHidden.value = String(val);
            if (kmeansOut) {
                kmeansOut.textContent = val === 0 ? 'خاموش' : String(val);
                kmeansOut.classList.toggle('is-off', val === 0);
            }
        };
        kmeansRange.addEventListener('input', syncKmeans);
        syncKmeans();
    }

    if (logoZone && logoInput) {
        logoZone.addEventListener('click', e => {
            if (e.target.tagName !== 'BUTTON') logoInput.click();
        });
        logoZone.addEventListener('dragover', e => {
            e.preventDefault();
            logoZone.classList.add('is-dragover');
        });
        logoZone.addEventListener('dragleave', () => logoZone.classList.remove('is-dragover'));
        logoZone.addEventListener('drop', e => {
            e.preventDefault();
            logoZone.classList.remove('is-dragover');
            if (e.dataTransfer.files.length) {
                logoInput.files = e.dataTransfer.files;
                onLogoSelect();
            }
        });
        logoInput.addEventListener('change', onLogoSelect);

        function onLogoSelect() {
            const file = logoInput.files[0];
            if (!file) return;
            if (logoFileName) logoFileName.textContent = '✓ ' + file.name;
            if (!file.type.startsWith('image/')) return;
            const reader = new FileReader();
            reader.onload = () => {
                if (!logoCurrent) return;
                logoCurrent.classList.remove('is-empty');
                let img = logoCurrent.querySelector('img');
                if (!img) {
                    const ph = logoCurrent.querySelector('.ws-settings-logo-placeholder');
                    if (ph) ph.remove();
                    img = document.createElement('img');
                    img.alt = 'پیش‌نمایش لوگو';
                    logoCurrent.appendChild(img);
                }
                img.src = reader.result;
            };
            reader.readAsDataURL(file);
        }
    }

    initShareProfileImagePreviews(form);

    form.addEventListener('submit', () => {
        const theme = form.querySelector('input[name="theme"]:checked')?.value;
        if (theme) {
            try { localStorage.setItem('ws-theme', theme); } catch (e) {}
        }
        const scale = fontHidden?.value;
        if (scale) html.style.setProperty('--ws-font-scale', scale);
    });
}

function initUploadZone() {
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('fileInput');
    const nameInput = document.getElementById('datasetName');
    const fileLabel = document.getElementById('uploadFileName');
    if (zone && input) {
        zone.addEventListener('click', e => {
            if (e.target.tagName !== 'BUTTON') input.click();
        });
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('is-dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('is-dragover'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('is-dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                onFileSelect();
            }
        });
        input.addEventListener('change', onFileSelect);

        function onFileSelect() {
            const file = input.files[0];
            if (!file) return;
            if (fileLabel) fileLabel.textContent = '✓ ' + file.name;
            if (nameInput && !nameInput.value) {
                nameInput.value = file.name.replace(/\.[^.]+$/, '');
            }
        }
    }

    const folderZone = document.getElementById('folderUploadZone');
    const folderInput = document.getElementById('folderInput');
    const folderForm = document.getElementById('uploadFolderForm');
    const folderPreview = document.getElementById('folderPreview');
    const folderPreviewTree = document.getElementById('folderPreviewTree');
    const folderPreviewSummary = document.getElementById('folderPreviewSummary');
    const folderSubmit = document.getElementById('folderSubmit');
    if (!folderZone || !folderInput || !folderForm) return;

    folderZone.addEventListener('click', e => {
        if (e.target.tagName !== 'BUTTON') folderInput.click();
    });

    folderInput.addEventListener('change', () => {
        const files = [...folderInput.files];
        if (!files.length) {
            if (folderPreview) folderPreview.hidden = true;
            if (folderSubmit) folderSubmit.disabled = true;
            return;
        }
        const { tree, importable, total } = groupFilesByLocation(files);
        if (folderPreviewTree) folderPreviewTree.innerHTML = renderFolderPreview(tree);
        if (folderPreviewSummary) {
            folderPreviewSummary.textContent = `${importable} فایل داده از ${total} فایل — تفکیک بر اساس مسیر پوشه`;
        }
        if (folderPreview) folderPreview.hidden = importable === 0;
        if (folderSubmit) folderSubmit.disabled = importable === 0;
    });

    folderForm.addEventListener('submit', e => {
        e.preventDefault();
        const files = [...folderInput.files].filter(f => isImportablePath(f.webkitRelativePath || f.name));
        if (!files.length) return;

        const csrf = folderForm.querySelector('[name=csrfmiddlewaretoken]');
        const formData = new FormData();
        if (csrf) formData.append('csrfmiddlewaretoken', csrf.value);
        const relativePaths = files.map(f => (f.webkitRelativePath || f.name).replace(/\\/g, '/'));
        formData.append('relative_paths', JSON.stringify(relativePaths));
        files.forEach((file, i) => {
            formData.append('files', file, relativePaths[i] || file.name);
        });

        if (folderSubmit) {
            folderSubmit.disabled = true;
            folderSubmit.innerHTML = '<i class="fas fa-spinner fa-spin"></i> در حال وارد کردن…';
        }

        const listUrl = folderForm.dataset.listUrl || '/workspace/datasets/?open=modal-batch-result';

        fetch(folderForm.action, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        }).then(async res => {
            let data = null;
            try {
                data = await res.json();
            } catch (_) {
                data = null;
            }
            if (data && data.ok && data.redirect) {
                window.location.assign(data.redirect);
                return;
            }
            if (data && !data.ok) {
                throw new Error(data.error || 'آپلود ناموفق بود.');
            }
            if (res.ok) {
                window.location.assign(listUrl);
                return;
            }
            throw new Error(data?.error || `خطای سرور (${res.status})`);
        }).catch(err => {
            if (folderSubmit) {
                folderSubmit.disabled = false;
                folderSubmit.innerHTML = '<i class="fas fa-layer-group"></i> وارد کردن همه';
            }
            alert(err.message || 'خطا در آپلود پوشه. دوباره تلاش کنید.');
        });
    });
}

function fmtAxisMoney(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return v;
    const abs = Math.abs(n);
    if (abs >= 1e9) return `${parseFloat((n / 1e9).toFixed(1))}B`;
    if (abs >= 1e6) return `${Math.round(n / 1e6)}M`;
    if (abs >= 1e3) return `${Math.round(n / 1e3)}K`;
    return `${Math.round(n)}`;
}

function fmtAxisArea(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return v;
    return `${Math.round(n)}m`;
}

function moneyTickCallback(value) {
    return fmtAxisMoney(value);
}

function chartThemeColors() {
    const dark = document.documentElement.dataset.theme !== 'light';
    return {
        grid: dark ? 'rgba(148, 163, 184, 0.08)' : 'rgba(0, 0, 0, 0.04)',
        text: dark ? '#94A3B8' : '#64748B',
        tooltipBg: dark ? '#1E293B' : '#FFFFFF',
        tooltipText: dark ? '#F1F5F9' : '#0F172A',
        tooltipBorder: dark ? 'rgba(148, 163, 184, 0.15)' : 'rgba(15, 23, 42, 0.08)',
    };
}

function hubLineGradient(canvas, color) {
    const ctx = canvas.getContext('2d');
    const h = canvas.parentElement?.clientHeight || 220;
    const g = ctx.createLinearGradient(0, 0, 0, h);
    if (color && color.startsWith('#') && color.length >= 7) {
        const r = parseInt(color.slice(1, 3), 16);
        const gr = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);
        g.addColorStop(0, `rgba(${r},${gr},${b},0.2)`);
        g.addColorStop(1, `rgba(${r},${gr},${b},0)`);
    } else {
        g.addColorStop(0, 'rgba(16, 185, 129, 0.18)');
        g.addColorStop(1, 'rgba(16, 185, 129, 0)');
    }
    return g;
}

function buildHubTrendLegend(chart) {
    const el = document.getElementById('hubTrendLegend');
    if (!el || !chart.datasets) return;
    el.innerHTML = chart.datasets.map(ds => (
        `<span class="mk-insight-legend-item" style="--leg-color:${ds.borderColor}">`
        + `<i aria-hidden="true"></i>${ds.label}</span>`
    )).join('');
    el.removeAttribute('aria-hidden');
}

function bindTrendRange(chart, chartConfig, canvas) {
    const wrap = canvas.closest('[data-trend-chart]')
        || canvas.closest('.mk-insight--trend')
        || canvas.closest('.crm-cell--trend');
    if (!wrap || !chartConfig.ranges) return;
    const titleEl = document.getElementById('hubTrendTitle')
        || document.getElementById('crmDashTrendTitle')
        || wrap.querySelector('[data-trend-title]');
    const buttons = wrap.querySelectorAll('[data-trend-range]');

    function applyRange(rangeKey) {
        const range = chartConfig.ranges[rangeKey];
        if (!range) return;
        chart.data.labels = range.labels;
        range.datasets.forEach((src, i) => {
            if (!chart.data.datasets[i]) return;
            chart.data.datasets[i].data = src.data;
            chart.data.datasets[i].pointRadius = rangeKey === '30' ? 0 : (src.pointRadius ?? 3);
            chart.data.datasets[i].pointHoverRadius = rangeKey === '30' ? 5 : (src.pointHoverRadius ?? 6);
        });
        if (chart.options.scales?.x?.ticks) {
            chart.options.scales.x.ticks.maxTicksLimit = rangeKey === '30' ? 8 : 7;
        }
        wrap.classList.toggle('is-trend-30', rangeKey === '30');
        wrap.classList.toggle('is-trend-7', rangeKey !== '30');
        chart.update();
        buttons.forEach(btn => {
            const active = btn.dataset.trendRange === rangeKey;
            btn.classList.toggle('is-active', active);
            btn.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        if (titleEl) titleEl.textContent = rangeKey === '30' ? 'روند ۳۰ روز' : 'روند ۷ روز';
        if (typeof buildHubTrendLegend === 'function') {
            buildHubTrendLegend({ datasets: chart.data.datasets });
        }
    }

    buttons.forEach(btn => {
        btn.addEventListener('click', () => applyRange(btn.dataset.trendRange));
    });
    wrap.classList.add('is-trend-7');
}

/** @deprecated use bindTrendRange */
function bindHubTrendRange(chart, chartConfig, canvas) {
    bindTrendRange(chart, chartConfig, canvas);
}

function initConfidenceRings() {
    document.querySelectorAll('.ws-rpt-l1-conf-ring[data-score]').forEach((el) => {
        const score = Math.min(100, Math.max(0, parseInt(el.dataset.score, 10) || 0));
        el.style.setProperty('--p', String(score));
    });
}

function initL2Tabs() {
    const studio = document.querySelector('.ws-rpt-l2-studio');
    if (!studio) return;
    const tabs = studio.querySelectorAll('.ws-rpt-l2-tab');
    const panels = studio.querySelectorAll('.ws-rpt-l2-tabpanel');

    function activatePanel(id) {
        tabs.forEach((t) => {
            const on = t.dataset.l2Tab === id;
            t.classList.toggle('is-active', on);
            t.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        panels.forEach((p) => {
            const on = p.dataset.l2Panel === id;
            p.classList.toggle('is-active', on);
            if (on) {
                p.removeAttribute('hidden');
                requestAnimationFrame(() => {
                    if (typeof initCharts === 'function' && window.wsCharts) {
                        initCharts(window.wsCharts);
                    }
                    p.querySelectorAll('canvas').forEach((c) => {
                        const inst = window.Chart && Chart.getChart(c);
                        if (inst) inst.resize();
                    });
                });
            } else {
                p.setAttribute('hidden', '');
            }
        });
    }

    tabs.forEach((btn) => {
        btn.addEventListener('click', () => activatePanel(btn.dataset.l2Tab));
    });
}

function initCharts(chartsData) {
    if (!chartsData || !window.Chart) return;
    const theme = chartThemeColors();
    const isHub = window.wsChartsHub === true || document.querySelector('.mk-hub-pro');
    const isMobileChart = window.matchMedia('(max-width: 768px)').matches;

    chartsData.forEach((chart, idx) => {
        const canvas = document.getElementById('chart-' + idx) || document.getElementById('chart-' + (chart.id || idx));
        if (!canvas) return;
        if (Chart.getChart(canvas)) return;

        const l2Panel = canvas.closest('.ws-rpt-l2-tabpanel');
        if (l2Panel && l2Panel.hidden) return;
        const isAnalyzeL2 = !!canvas.closest('.ws-rpt-l2-studio');

        const isTrendCell = !!(canvas.closest('.crm-cell--trend') || canvas.closest('[data-trend-chart]'));
        const useTrendStyle = isHub || isTrendCell;

        if (chart.type === 'line') {
            const datasets = chart.datasets.map((ds, i) => {
                const copy = {
                    ...ds,
                    borderWidth: useTrendStyle ? 2.25 : (ds.borderWidth || 2),
                    pointRadius: useTrendStyle ? 0 : (ds.pointRadius ?? 3),
                    pointHoverRadius: useTrendStyle ? 5 : (ds.pointHoverRadius ?? 6),
                    tension: 0.42,
                };
                if (useTrendStyle && ds.fill && ds.borderColor) {
                    copy.backgroundColor = hubLineGradient(canvas, ds.borderColor || '#10B981');
                    copy.fill = true;
                }
                if (useTrendStyle) copy.pointBackgroundColor = ds.borderColor;
                return copy;
            });
            if (isHub) buildHubTrendLegend(chart);
            const chartInstance = new Chart(canvas, {
                type: 'line',
                data: { labels: chart.labels, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    animation: useTrendStyle ? { duration: 750, easing: 'easeOutQuart' } : undefined,
                    plugins: {
                        legend: { display: !useTrendStyle, position: 'top', align: 'end', labels: { color: theme.text, font: { family: 'Vazirmatn', size: 11 }, boxWidth: 12, padding: 16 } },
                        tooltip: {
                            backgroundColor: theme.tooltipBg,
                            titleColor: theme.tooltipText,
                            bodyColor: theme.tooltipText,
                            borderColor: theme.tooltipBorder,
                            borderWidth: 1,
                            padding: isHub ? 14 : 12,
                            cornerRadius: 10,
                            displayColors: true,
                            boxPadding: 4,
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: useTrendStyle ? false : true, color: theme.grid },
                            ticks: {
                                color: theme.text,
                                font: { family: 'Vazirmatn', size: useTrendStyle ? (isMobileChart ? 9 : 10) : 11 },
                                maxRotation: isMobileChart && useTrendStyle ? 40 : 0,
                                maxTicksLimit: useTrendStyle ? (isMobileChart ? 5 : 7) : undefined,
                                autoSkip: true,
                            },
                            border: { display: false },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: theme.grid, drawTicks: false },
                            ticks: { color: theme.text, stepSize: 1, font: { family: 'Vazirmatn', size: 10 }, padding: 8 },
                            border: { display: false },
                        },
                    },
                },
            });
            if (chart.ranges) bindTrendRange(chartInstance, chart, canvas);
            return;
        }

        if (chart.type === 'doughnut') {
            const total = chart.datasets[0].data.reduce((a, b) => a + b, 0);
            const ds = isHub ? [{ ...chart.datasets[0], borderRadius: 5, spacing: 2, hoverOffset: 8 }] : chart.datasets;
            const doughnutOpts = {
                responsive: true,
                maintainAspectRatio: false,
                cutout: isHub ? '76%' : (isAnalyzeL2 ? '68%' : '72%'),
                animation: isHub ? { animateRotate: true, duration: 800 } : undefined,
                plugins: {
                    legend: {
                        display: !isHub,
                        position: isAnalyzeL2 ? 'bottom' : 'left',
                        labels: {
                            color: theme.text,
                            font: { family: 'Vazirmatn', size: isAnalyzeL2 ? 10 : 11 },
                            boxWidth: 10,
                            padding: isAnalyzeL2 ? 8 : 10,
                        },
                    },
                    tooltip: {
                        backgroundColor: theme.tooltipBg,
                        titleColor: theme.tooltipText,
                        bodyColor: theme.tooltipText,
                        borderColor: theme.tooltipBorder,
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 10,
                        callbacks: {
                            label(ctx) {
                                const pct = total ? Math.round(ctx.parsed / total * 100) : 0;
                                return `${ctx.label}: ${ctx.parsed} (${pct}%)`;
                            },
                        },
                    },
                },
            };
            new Chart(canvas, {
                type: 'doughnut',
                data: { labels: chart.labels, datasets: ds },
                options: doughnutOpts,
            });
            return;
        }

        const isScatter = chart.type === 'scatter';
        const isHorizontal = chart.horizontal;
        const axisType = chart.axis || (isScatter ? null : 'money');
        const yAxisType = chart.yAxis || (isScatter ? 'money' : null);
        const xAxisType = chart.xAxis || (isScatter ? 'area' : null);

        const isMinimal = chart.minimal === true;
        const isCount = chart.axis === 'count';

        const opts = {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: isScatter && !isMinimal, labels: { font: { family: 'Vazirmatn' }, color: theme.text } },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipText,
                    bodyColor: theme.tooltipText,
                    callbacks: {
                        label(ctx) {
                            if (isScatter) {
                                return `متراژ ${ctx.parsed.x}m — قیمت ${fmtAxisMoney(ctx.parsed.y)}`;
                            }
                            const v = ctx.parsed.y ?? ctx.parsed.x;
                            if (chart.axis === 'percent') {
                                return `${ctx.dataset.label}: ${v}٪`;
                            }
                            if (chart.dual_axis || axisType === 'money') {
                                return `${ctx.dataset.label}: ${fmtAxisMoney(v)}`;
                            }
                            return isCount ? `${v} مورد` : `${ctx.dataset.label}: ${v}`;
                        },
                    },
                },
            },
            scales: {},
        };

        if (isMinimal) {
            opts.plugins.legend.display = false;
            opts.layout = { padding: { top: 4, bottom: 0, left: 0, right: 4 } };
        }

        if (isScatter) {
            opts.scales.x = {
                title: { display: true, text: 'متراژ (m)' },
                ticks: { callback: fmtAxisArea },
            };
            opts.scales.y = {
                title: { display: true, text: 'قیمت (M/B)' },
                ticks: { callback: moneyTickCallback },
            };
        } else if (isHorizontal) {
            opts.indexAxis = 'y';
            opts.scales.x = {
                title: { display: !isMinimal, text: chart.unit || (isCount ? '' : 'M/B') },
                ticks: {
                    callback: isCount ? (v) => (Number.isInteger(v) ? v : '') : moneyTickCallback,
                    stepSize: isCount ? 1 : undefined,
                },
                grid: { display: !isMinimal, color: 'rgba(0,0,0,.04)' },
                border: { display: false },
            };
            opts.scales.y = {
                grid: { display: false },
                border: { display: false },
                ticks: { font: { family: 'Vazirmatn', size: 11 } },
            };
        } else if (isCount || axisType === 'count') {
            opts.scales.y = {
                beginAtZero: true,
                title: { display: false },
                ticks: { stepSize: 1, precision: 0, font: { family: 'Vazirmatn', size: 11 } },
                grid: { display: !isMinimal, color: 'rgba(0,0,0,.04)' },
                border: { display: false },
            };
            opts.scales.x = {
                grid: { display: false },
                border: { display: false },
                ticks: { font: { family: 'Vazirmatn', size: 11 } },
            };
        } else if (chart.dual_axis) {
            opts.scales.y = {
                type: 'linear',
                position: 'left',
                title: { display: true, text: 'قیمت/متر', color: theme.text },
                ticks: { callback: moneyTickCallback, color: theme.text },
                grid: { color: theme.grid },
            };
            opts.scales.y1 = {
                type: 'linear',
                position: 'right',
                title: { display: true, text: 'قیمت کل', color: theme.text },
                ticks: { callback: moneyTickCallback, color: theme.text },
                grid: { drawOnChartArea: false },
            };
            chart.datasets.forEach((ds, i) => {
                ds.yAxisID = ds.yAxisID || (i === 0 ? 'y' : 'y1');
            });
            opts.plugins.legend = { display: true, labels: { color: theme.text, font: { family: 'Vazirmatn' } } };
        } else if (axisType === 'percent') {
            opts.scales.y = {
                beginAtZero: true,
                max: 100,
                title: { display: true, text: chart.unit || '٪' },
                ticks: { callback: (v) => `${v}٪`, font: { family: 'Vazirmatn', size: 11 } },
                grid: { color: 'rgba(0,0,0,.04)' },
            };
            opts.scales.x = {
                grid: { display: false },
                ticks: { font: { family: 'Vazirmatn', size: 11 } },
            };
        } else if (axisType === 'money') {
            opts.scales.y = {
                title: { display: true, text: chart.unit || 'M/B' },
                ticks: { callback: moneyTickCallback },
            };
        } else if (axisType === 'area') {
            opts.scales.y = { title: { display: true, text: 'متر' } };
        }

        if (isAnalyzeL2 && !isScatter) {
            opts.maintainAspectRatio = false;
            opts.layout = { padding: { top: 8, bottom: 4, left: 4, right: 8 } };
            chart.datasets = chart.datasets.map((ds) => ({
                ...ds,
                maxBarThickness: 52,
                borderRadius: isHorizontal ? 4 : 6,
            }));
            if (opts.scales.x && !isHorizontal) {
                opts.scales.x.ticks = {
                    ...(opts.scales.x.ticks || {}),
                    maxRotation: 35,
                    minRotation: 0,
                    maxTicksLimit: 8,
                    autoSkip: true,
                    font: { family: 'Vazirmatn', size: 10 },
                };
                opts.scales.x.grid = { display: false };
            }
            if (opts.scales.y) {
                opts.scales.y.grid = { color: 'rgba(0,0,0,.05)', drawTicks: false };
                opts.scales.y.ticks = {
                    ...(opts.scales.y.ticks || {}),
                    font: { family: 'Vazirmatn', size: 10 },
                    padding: 6,
                };
            }
        }

        new Chart(canvas, {
            type: isScatter ? 'scatter' : 'bar',
            data: { labels: chart.labels, datasets: chart.datasets },
            options: opts,
        });
    });
}

function wsEscapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function mapSellerKind(m) {
    const sig = String(m.advertiser_signal || '');
    const label = String(m.seller_type || '');
    if (sig === 'disguised_consultant' || m.is_disguised || label === 'مشاور پنهان') return 'disguised';
    if (sig === 'consultant' || m.is_consultant || label === 'مشاور') return 'consultant';
    if (sig === 'genuine_personal' || label === 'مالک واقعی' || label === 'مالک') return 'genuine';
    return 'personal';
}

function mapSellerLabel(m) {
    if (m.seller_type) return m.seller_type;
    const kind = mapSellerKind(m);
    if (kind === 'disguised') return 'مشاور پنهان';
    if (kind === 'consultant') return 'مشاور';
    if (kind === 'genuine') return 'مالک واقعی';
    return 'شخصی';
}

function buildMapMarkerPopup(m) {
    const priceLine = m.price_label || (m.price ? Number(m.price).toLocaleString('fa-IR') : '—');
    const sellerClass = mapSellerKind(m);
    const sellerLabel = mapSellerLabel(m);
    const locParts = [m.city, m.neighborhood].filter(Boolean);
    const locLine = locParts.length ? locParts.join(' · ') : '';

    const chips = [];
    if (m.area_label || m.area) chips.push({ icon: 'fa-ruler-combined', value: m.area_label || `${m.area} متر` });
    if (m.rooms) chips.push({ icon: 'fa-door-open', value: `${m.rooms} خواب` });
    if (m.pps_label) chips.push({ icon: 'fa-chart-line', value: m.pps_label });
    if (m.deposit_label) chips.push({ icon: 'fa-hand-holding-usd', value: m.deposit_label.startsWith('ودیعه') ? m.deposit_label : `ودیعه ${m.deposit_label}` });
    if (m.rent_label) chips.push({ icon: 'fa-calendar-alt', value: m.rent_label.startsWith('اجاره') ? m.rent_label : `اجاره ${m.rent_label}` });

    const chipsHtml = chips.length
        ? `<div class="mk-map-popup-chips">${chips.map(c =>
            `<span class="mk-map-popup-chip"><i class="fas ${c.icon}" aria-hidden="true"></i>${wsEscapeHtml(c.value)}</span>`
        ).join('')}</div>`
        : '';

    const thumbHtml = m.thumb
        ? `<div class="mk-map-popup-media"><img src="${wsEscapeHtml(m.thumb)}" alt="" loading="lazy"></div>`
        : '';

    const locAccIcon = m.location_kind === 'exact' ? 'fa-crosshairs' : 'fa-circle-notch';
    const locAccHtml = m.location_label
        ? `<span class="mk-map-popup-meta-item mk-map-popup-meta-item--loc-${wsEscapeHtml(m.location_kind || 'approx')}"><i class="fas ${locAccIcon}" aria-hidden="true"></i>${wsEscapeHtml(m.location_label)}</span>`
        : '';

    const verdictClass = {
        under: 'under',
        fair: 'fair',
        over: 'over',
    }[m.market_tier] || '';
    const verdictHtml = m.verdict && verdictClass
        ? `<span class="mk-map-popup-verdict mk-map-popup-verdict--${verdictClass}">${wsEscapeHtml(m.verdict)}</span>`
        : (m.verdict ? `<span class="mk-map-popup-verdict">${wsEscapeHtml(m.verdict)}</span>` : '');

    const metaHtml = (m.published && m.published !== '—') || locLine || m.location_label
        ? `<div class="mk-map-popup-meta">
            ${locAccHtml}
            ${locLine ? `<span class="mk-map-popup-meta-item"><i class="fas fa-map-marker-alt" aria-hidden="true"></i>${wsEscapeHtml(locLine)}</span>` : ''}
            ${m.published && m.published !== '—' ? `<span class="mk-map-popup-meta-item"><i class="far fa-clock" aria-hidden="true"></i>${wsEscapeHtml(m.published)}</span>` : ''}
        </div>`
        : '';

    const platformBtn = m.platform_url
        ? `<a href="${wsEscapeHtml(m.platform_url)}" class="mk-map-popup-btn mk-map-popup-btn--filing"><i class="fas fa-folder-open" aria-hidden="true"></i><span>مشاهده فایل</span></a>`
        : '';
    const divarBtn = m.link
        ? `<a href="${wsEscapeHtml(m.link)}" target="_blank" rel="noopener noreferrer" class="mk-map-popup-btn mk-map-popup-btn--divar"><i class="fas fa-external-link-alt" aria-hidden="true"></i><span>دیوار</span></a>`
        : '';

    return `
        <article class="mk-map-popup mk-map-popup--card mk-map-popup--${sellerClass}">
            ${thumbHtml}
            <div class="mk-map-popup-body">
                <div class="mk-map-popup-head">
                    <span class="mk-map-popup-badge mk-map-popup-badge--${sellerClass}">${wsEscapeHtml(sellerLabel)}</span>
                    ${m.token ? `<span class="mk-map-popup-token" dir="ltr">#${wsEscapeHtml(m.token)}</span>` : ''}
                </div>
                <h3 class="mk-map-popup-title">${wsEscapeHtml(m.title || 'بدون عنوان')}</h3>
                <div class="mk-map-popup-price-block">
                    <span class="mk-map-popup-price">${wsEscapeHtml(priceLine)}</span>
                    ${verdictHtml}
                </div>
                ${chipsHtml}
                ${metaHtml}
                ${(platformBtn || divarBtn) ? `<div class="mk-map-popup-actions">${divarBtn}${platformBtn}</div>` : ''}
            </div>
        </article>`;
}

function formatMapMoney(n, perSqm = false) {
    const v = Number(n) || 0;
    if (!v) return '—';
    const suffix = perSqm ? ' /متر' : '';
    if (v >= 1_000_000_000) {
        const b = (v / 1_000_000_000).toLocaleString('fa-IR', { maximumFractionDigits: 1 });
        return `${b} میلیارد${suffix}`;
    }
    if (v >= 1_000_000) {
        const m = (v / 1_000_000).toLocaleString('fa-IR', { maximumFractionDigits: 0 });
        return `${m} میلیون${suffix}`;
    }
    return `${v.toLocaleString('fa-IR')}${suffix}`;
}

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹';

function toAsciiDigits(str) {
    return String(str ?? '').replace(/[۰-۹]/g, (ch) => {
        const i = FA_DIGITS.indexOf(ch);
        return i >= 0 ? String(i) : '';
    });
}

function parseFormattedNumber(val) {
    const s = toAsciiDigits(val).replace(/[^\d.]/g, '');
    if (!s) return '';
    const n = Number(s);
    return Number.isFinite(n) ? String(n) : '';
}

function formatWithSeparators(val) {
    const raw = parseFormattedNumber(val);
    if (!raw) return '';
    const n = Number(raw);
    if (!Number.isFinite(n)) return '';
    return n.toLocaleString('fa-IR');
}

function readFormattedInput(el) {
    if (!el) return '';
    if (el.dataset.rawValue != null && el.dataset.rawValue !== '') return el.dataset.rawValue;
    return parseFormattedNumber(el.value);
}

function bindFormattedNumericInput(el, { onChange } = {}) {
    if (!el || el.dataset.fmtBound === '1') return;
    el.dataset.fmtBound = '1';
    if (el.type === 'number') el.type = 'text';
    el.setAttribute('inputmode', 'numeric');
    el.setAttribute('autocomplete', 'off');
    el.classList.add('mk-filter-num');

    const applyFormat = () => {
        const raw = parseFormattedNumber(el.value);
        const formatted = raw ? formatWithSeparators(raw) : '';
        el.dataset.rawValue = raw;
        el.value = formatted;
        onChange?.(raw);
    };

    el.addEventListener('input', applyFormat);
    if (el.value) applyFormat();
}

function initFormattedNumericInputs(root = document) {
    const mapFmtIds = new Set(['mkMapPriceMin', 'mkMapPriceMax', 'mkMapAreaMin', 'mkMapAreaMax']);
    root.querySelectorAll('.mk-filter-num, .mk-filter-ranges input[type="number"]').forEach((el) => {
        if (mapFmtIds.has(el.id)) return;
        bindFormattedNumericInput(el);
    });
    root.querySelectorAll('form').forEach((form) => {
        if (form.dataset.fmtSubmitBound === '1') return;
        if (!form.querySelector('.mk-filter-num')) return;
        form.dataset.fmtSubmitBound = '1';
        form.addEventListener('submit', () => {
            form.querySelectorAll('.mk-filter-num').forEach((el) => {
                const raw = readFormattedInput(el);
                el.value = raw;
                el.dataset.rawValue = raw;
            });
        });
    });
}

const MAP_VPN_TIP_KEY = 'ws_map_vpn_tip_dismissed';

const MAP_VALUE_TIER_COLORS = ['#94a3b8', '#06b6d4', '#4f46e5', '#9333ea', '#d97706', '#b91c1c'];

/** گرادیان‌های هیت‌مپ — هم‌راستا با تحلیل بازار (cyan→قرمز / آبی→قرمز) */
const HEAT_COLOR_STOPS = {
    density: [
        [0, '#22d3ee'],
        [0.18, '#38bdf8'],
        [0.32, '#facc15'],
        [0.48, '#fb923c'],
        [0.65, '#f97316'],
        [0.82, '#ef4444'],
        [1, '#7f1d1d'],
    ],
    price: [
        [0, '#2563eb'],
        [0.22, '#0d9488'],
        [0.42, '#14b8a6'],
        [0.58, '#eab308'],
        [0.74, '#f97316'],
        [0.88, '#ef4444'],
        [1, '#991b1b'],
    ],
    pps: [
        [0, '#6ee7b7'],
        [0.2, '#22d3ee'],
        [0.38, '#6366f1'],
        [0.55, '#a855f7'],
        [0.72, '#f59e0b'],
        [0.88, '#ea580c'],
        [1, '#b91c1c'],
    ],
};

function parseHexRgb(hex) {
    const h = String(hex || '').replace('#', '');
    if (h.length !== 6) return [0, 0, 0];
    return [
        parseInt(h.slice(0, 2), 16),
        parseInt(h.slice(2, 4), 16),
        parseInt(h.slice(4, 6), 16),
    ];
}

function interpolateHexColor(c0, c1, u) {
    const [r0, g0, b0] = parseHexRgb(c0);
    const [r1, g1, b1] = parseHexRgb(c1);
    const r = Math.round(r0 + u * (r1 - r0));
    const g = Math.round(g0 + u * (g1 - g0));
    const b = Math.round(b0 + u * (b1 - b0));
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

function heatColorAt(t, palette = 'density') {
    const stops = HEAT_COLOR_STOPS[palette] || HEAT_COLOR_STOPS.density;
    const clamped = Math.max(0, Math.min(1, t));
    for (let i = 0; i < stops.length - 1; i++) {
        const [t0, c0] = stops[i];
        const [t1, c1] = stops[i + 1];
        if (clamped <= t1) {
            const u = t1 === t0 ? 0 : (clamped - t0) / (t1 - t0);
            return interpolateHexColor(c0, c1, u);
        }
    }
    return stops[stops.length - 1][1];
}

function buildLeafletHeatGradient(palette) {
    const stops = HEAT_COLOR_STOPS[palette] || HEAT_COLOR_STOPS.density;
    const gradient = {};
    gradient[0.1] = stops[0][1];
    stops.forEach(([t, hex]) => {
        gradient[t] = hex;
    });
    return gradient;
}

function cssGradientFromStops(palette) {
    const stops = HEAT_COLOR_STOPS[palette] || HEAT_COLOR_STOPS.density;
    const parts = stops.map(([t, c]) => `${c} ${Math.round(t * 100)}%`);
    return `linear-gradient(90deg, ${parts.join(', ')})`;
}

function normalizeHeatValues(values) {
    const positives = values.filter(v => v > 0);
    const minVal = positives.length ? Math.min(...positives) : 0;
    const maxVal = positives.length ? Math.max(...positives) : 0;
    return values.map((v) => {
        if (!v || v <= 0) return 0.12;
        if (maxVal <= minVal) return 0.55;
        return 0.15 + 0.85 * ((v - minVal) / (maxVal - minVal));
    });
}

function mapHasView(map) {
    if (!map || typeof map.getZoom !== 'function') return false;
    try {
        if (map._loaded === false) return false;
        const z = map.getZoom();
        const c = map.getCenter();
        return Number.isFinite(z) && c && Number.isFinite(c.lat) && Number.isFinite(c.lng);
    } catch (e) {
        return false;
    }
}

function computeHeatLayerOptions(source, palette, map, { weighted = false } = {}) {
    const count = source.length;
    const logFactor = Math.log10(Math.max(count, 10));
    let radius = Math.min(80, Math.max(38, Math.round(34 + logFactor * 6)));
    if (count < 60) radius = Math.max(radius, 52);
    if (mapHasView(map) && source.length > 1 && window.L) {
        try {
            const bounds = L.latLngBounds(source.map(m => [m.lat, m.lng]));
            const sw = map.latLngToContainerPoint(bounds.getSouthWest());
            const ne = map.latLngToContainerPoint(bounds.getNorthEast());
            const span = Math.max(Math.abs(ne.x - sw.x), Math.abs(ne.y - sw.y), 1);
            const adaptive = Math.round(span * 0.065);
            radius = Math.min(90, Math.max(radius, adaptive));
        } catch (e) { /* map not ready yet */ }
    }
    const blur = Math.round(radius * 0.85);
    // leaflet-heat: شدت *= 2^-(maxZoom - zoom فعلی) — maxZoom باید زوم فعلی باشد
    const zoom = mapHasView(map) ? map.getZoom() : 13;
    const maxZoom = zoom;
    return {
        radius,
        blur,
        minOpacity: 0.38,
        maxZoom,
        max: 1.0,
        gradient: buildLeafletHeatGradient(palette),
    };
}

function rgbaFromHex(hex, alpha) {
    const [r, g, b] = parseHexRgb(hex);
    return `rgba(${r},${g},${b},${alpha})`;
}

/** لایه هیت‌مپ اختصاصی — جایگزین leaflet-heat که روی برخی مرورگرها درست رندر نمی‌شود */
function createMkHeatLayer(points, map, { palette = 'density', weighted = false, source = null, radius = 50 } = {}) {
    if (!window.L) return L.layerGroup();

    const MkHeatLayer = L.Layer.extend({
        initialize(pts, opts) {
            this._points = pts || [];
            this._opts = opts || {};
            this._radius = opts.radius || 50;
            this._palette = opts.palette || 'density';
            this._weighted = !!opts.weighted;
            this._source = opts.source || null;
        },
        onAdd(m) {
            this._map = m;
            if (!m.getPane('mkHeatPane')) {
                const pane = m.createPane('mkHeatPane');
                pane.style.zIndex = '650';
                pane.style.pointerEvents = 'none';
            }
            this._canvas = L.DomUtil.create('canvas', 'leaflet-heatmap-layer mk-heat-canvas');
            this._canvas.style.pointerEvents = 'none';
            m.getPane('mkHeatPane').appendChild(this._canvas);
            this._onReset = () => this._reset();
            m.on('moveend zoomend resize viewreset', this._onReset, this);
            this._reset();
        },
        onRemove(m) {
            m.off('moveend zoomend resize viewreset', this._onReset, this);
            if (this._canvas?.parentNode) this._canvas.parentNode.removeChild(this._canvas);
            this._canvas = null;
        },
        setOptions(opts = {}) {
            if (opts.radius != null) this._radius = opts.radius;
            if (opts.palette) this._palette = opts.palette;
            if (opts.gradient) { /* گرادیان در paint محاسبه می‌شود */ }
            this._reset();
            return this;
        },
        setLatLngs(pts) {
            this._points = pts || [];
            this._reset();
            return this;
        },
        redraw() {
            this._reset();
            return this;
        },
        _reset() {
            if (!this._map || !this._canvas) return;
            const m = this._map;
            const size = m.getSize();
            const topLeft = m.containerPointToLayerPoint([0, 0]);
            L.DomUtil.setPosition(this._canvas, topLeft);
            const w = Math.max(1, size.x | 0);
            const h = Math.max(1, size.y | 0);
            if (this._canvas.width !== w) this._canvas.width = w;
            if (this._canvas.height !== h) this._canvas.height = h;
            this._paint();
        },
        _paint() {
            const ctx = this._canvas.getContext('2d');
            if (!ctx) return;
            const w = this._canvas.width;
            const h = this._canvas.height;
            ctx.clearRect(0, 0, w, h);
            const m = this._map;
            const points = this._points;
            if (!points.length) return;

            const topLeft = m.containerPointToLayerPoint([0, 0]);
            const radius = this._radius || 50;
            const palette = this._palette || 'density';

            ctx.save();
            ctx.globalCompositeOperation = 'lighter';
            points.forEach((pt) => {
                const lat = Number(pt[0]);
                const lng = Number(pt[1]);
                if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
                const raw = Number(pt[2]) || 1;
                const layerPt = m.latLngToLayerPoint([lat, lng]);
                const x = layerPt.x - topLeft.x;
                const y = layerPt.y - topLeft.y;
                if (x < -radius || y < -radius || x > w + radius || y > h + radius) return;

                const t = this._weighted
                    ? Math.max(0.2, Math.min(1, raw))
                    : Math.max(0.4, Math.min(1, raw / 2.2));
                const color = heatColorAt(t, palette);
                const grad = ctx.createRadialGradient(x, y, 0, x, y, radius);
                grad.addColorStop(0, rgbaFromHex(color, 0.7));
                grad.addColorStop(0.3, rgbaFromHex(color, 0.42));
                grad.addColorStop(0.65, rgbaFromHex(color, 0.16));
                grad.addColorStop(1, rgbaFromHex(color, 0));
                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(x, y, radius, 0, Math.PI * 2);
                ctx.fill();
            });
            ctx.restore();
        },
    });

    const layer = new MkHeatLayer(points, { palette, weighted, source, radius });
    layer._isHeatLayer = true;
    layer._heatPalette = palette;
    layer._heatWeighted = weighted;
    layer._heatSource = source;
    return layer;
}

function valueTierColor(tier) {
    return MAP_VALUE_TIER_COLORS[tier] || MAP_VALUE_TIER_COLORS[0];
}

function setupMapVpnTip(mapLayer) {
    const tip = document.getElementById('mkMapVpnTip');
    const closeBtn = document.getElementById('mkMapVpnTipClose');
    if (!tip || !closeBtn) return;

    function showTip() {
        tip.hidden = false;
    }

    function hideTip(persist = false) {
        tip.hidden = true;
        if (persist) {
            try { localStorage.setItem(MAP_VPN_TIP_KEY, '1'); } catch (e) { /* ignore */ }
        }
    }

    try {
        if (localStorage.getItem(MAP_VPN_TIP_KEY) === '1') {
            tip.hidden = true;
        }
    } catch (e) { /* ignore */ }

    closeBtn.addEventListener('click', () => hideTip(true));
    mapLayer?.on?.('tileerror', showTip);
}

const MAP_MARKET_COLORS = {
    under: '#059669',
    fair: '#6366f1',
    over: '#dc2626',
    unknown: '#94a3b8',
};

function parseRoomsCount(raw) {
    const n = parseInt(String(raw || '').replace(/[^\d]/g, ''), 10);
    return Number.isFinite(n) ? n : null;
}

function matchRoomsFilter(markerRooms, filter) {
    if (!filter || filter === 'all') return true;
    const n = parseRoomsCount(markerRooms);
    if (n == null) return false;
    if (filter === '4+') return n >= 4;
    return n === parseInt(filter, 10);
}

function matchFreshnessFilter(publishedTs, filter) {
    if (!filter || filter === 'all') return true;
    if (!publishedTs) return false;
    const days = { 1: 1, 7: 7, 30: 30 }[filter];
    if (!days) return true;
    return Date.now() - publishedTs <= days * 86400000;
}

function computeMapFilterBounds(markers, settings = {}) {
    const values = markers.map(m => Number(m.filter_value) || 0).filter(v => v > 0);
    const areas = markers.map(m => Number(m.area) || 0).filter(v => v > 0);
    return {
        priceMin: values.length ? Math.min(...values) : 0,
        priceMax: values.length ? Math.max(...values) : 0,
        areaMin: areas.length ? Math.min(...areas) : 0,
        areaMax: areas.length ? Math.max(...areas) : 0,
        priceLabel: settings.filterValueLabel || settings.filter_value_label || 'قیمت',
        isRent: !!(settings.isRent || settings.is_rent),
    };
}

function countActiveMapFilters(filterState) {
    let n = 0;
    if (filterState.txMode && filterState.txMode !== 'all') n += 1;
    if (filterState.neighborhood) n += 1;
    if (filterState.priceMin != null && filterState.priceMin !== '') n += 1;
    if (filterState.priceMax != null && filterState.priceMax !== '') n += 1;
    if (filterState.depositMin != null && filterState.depositMin !== '') n += 1;
    if (filterState.depositMax != null && filterState.depositMax !== '') n += 1;
    if (filterState.rentMin != null && filterState.rentMin !== '') n += 1;
    if (filterState.rentMax != null && filterState.rentMax !== '') n += 1;
    if (filterState.areaMin != null && filterState.areaMin !== '') n += 1;
    if (filterState.areaMax != null && filterState.areaMax !== '') n += 1;
    if (filterState.rooms && filterState.rooms !== 'all') n += 1;
    if (filterState.yearMin != null && filterState.yearMin !== '') n += 1;
    if (filterState.yearMax != null && filterState.yearMax !== '') n += 1;
    if (filterState.freshness && filterState.freshness !== 'all') n += 1;
    if (filterState.valueTier && filterState.valueTier !== 'all') n += 1;
    if (filterState.elevator) n += 1;
    if (filterState.parking) n += 1;
    if (filterState.storage) n += 1;
    return n;
}

function matchAmenityFilter(markerValue, required) {
    if (!required) return true;
    return markerValue === true;
}

function matchValueTierFilter(marketTier, filter) {
    if (!filter || filter === 'all') return true;
    return marketTier === filter;
}

function matchTxModeFilter(txMode, filter) {
    if (!filter || filter === 'all') return true;
    return txMode === filter;
}

function normalizeMoneyInput(val) {
    const n = Number(parseFormattedNumber(val) || val);
    if (!n || n <= 0) return null;
    if (n < 100000) return Math.round(n * 1_000_000);
    return n;
}

function applyMapMarkerFilters(markers, filterState, sellerFilter) {
    let list = markers;
    if (sellerFilter === 'consultant') {
        list = list.filter(m => mapSellerKind(m) === 'consultant');
    } else if (sellerFilter === 'disguised') {
        list = list.filter(m => mapSellerKind(m) === 'disguised');
    } else if (sellerFilter === 'genuine' || sellerFilter === 'personal') {
        // مالک واقعی + شخصی طبقه‌بندی‌نشده
        list = list.filter(m => {
            const kind = mapSellerKind(m);
            return kind === 'genuine' || kind === 'personal';
        });
    }

    const pMin = filterState.priceMin != null && filterState.priceMin !== '' ? normalizeMoneyInput(filterState.priceMin) : null;
    const pMax = filterState.priceMax != null && filterState.priceMax !== '' ? normalizeMoneyInput(filterState.priceMax) : null;
    const dMin = filterState.depositMin != null && filterState.depositMin !== '' ? normalizeMoneyInput(filterState.depositMin) : null;
    const dMax = filterState.depositMax != null && filterState.depositMax !== '' ? normalizeMoneyInput(filterState.depositMax) : null;
    const rMin = filterState.rentMin != null && filterState.rentMin !== '' ? normalizeMoneyInput(filterState.rentMin) : null;
    const rMax = filterState.rentMax != null && filterState.rentMax !== '' ? normalizeMoneyInput(filterState.rentMax) : null;
    const aMin = filterState.areaMin != null && filterState.areaMin !== '' ? Number(parseFormattedNumber(filterState.areaMin) || filterState.areaMin) : null;
    const aMax = filterState.areaMax != null && filterState.areaMax !== '' ? Number(parseFormattedNumber(filterState.areaMax) || filterState.areaMax) : null;
    const yMin = filterState.yearMin != null && filterState.yearMin !== '' ? Number(parseFormattedNumber(filterState.yearMin) || filterState.yearMin) : null;
    const yMax = filterState.yearMax != null && filterState.yearMax !== '' ? Number(parseFormattedNumber(filterState.yearMax) || filterState.yearMax) : null;

    return list.filter((m) => {
        if (!matchTxModeFilter(m.tx_mode, filterState.txMode)) return false;
        if (filterState.neighborhood && (m.neighborhood || '') !== filterState.neighborhood) return false;
        const fv = Number(m.filter_value) || 0;
        const area = Number(m.area) || 0;
        const deposit = Number(m.deposit) || 0;
        const rent = Number(m.rent) || 0;
        if (pMin != null && fv > 0 && fv < pMin) return false;
        if (pMax != null && fv > 0 && fv > pMax) return false;
        if (dMin != null && deposit > 0 && deposit < dMin) return false;
        if (dMax != null && deposit > 0 && deposit > dMax) return false;
        if (rMin != null && rent > 0 && rent < rMin) return false;
        if (rMax != null && rent > 0 && rent > rMax) return false;
        if (aMin != null && area > 0 && area < aMin) return false;
        if (aMax != null && area > 0 && area > aMax) return false;
        if (!matchRoomsFilter(m.rooms, filterState.rooms)) return false;
        if (yMin != null || yMax != null) {
            const year = Number(m.build_year) || 0;
            if (!year) return false;
            if (yMin != null && year < yMin) return false;
            if (yMax != null && year > yMax) return false;
        }
        if (!matchFreshnessFilter(m.published_ts, filterState.freshness)) return false;
        if (!matchValueTierFilter(m.market_tier, filterState.valueTier)) return false;
        if (!matchAmenityFilter(m.elevator, filterState.elevator)) return false;
        if (!matchAmenityFilter(m.parking, filterState.parking)) return false;
        if (!matchAmenityFilter(m.storage, filterState.storage)) return false;
        return true;
    });
}

function addAccuracyRings(group, marker, showRings) {
    if (!showRings || !marker.location_radius_m) return;
    const kind = mapSellerKind(marker);
    const stroke = {
        consultant: '#2563eb',
        disguised: '#be123c',
        genuine: '#059669',
        personal: '#e11d48',
    }[kind] || '#e11d48';
    const circle = L.circle([marker.lat, marker.lng], {
        radius: marker.location_radius_m,
        color: stroke,
        fillColor: stroke,
        fillOpacity: 0.07,
        weight: 1.5,
        opacity: 0.42,
        className: 'mk-map-area-ring',
    });
    circle.bindPopup(buildMapMarkerPopup(marker), { className: 'mk-map-popup-shell', maxWidth: 300, minWidth: 260 });
    group.addLayer(circle);
}

function buildMapListItemHtml(m) {
    const tier = m.market_tier || 'unknown';
    const tierLabel = { under: 'زیر بازار', fair: 'متعارف', over: 'بالای بازار', unknown: '' }[tier] || '';
    const loc = [m.neighborhood, m.city].filter(Boolean).join(' · ');
    return `<button type="button" class="mk-map-list-item" data-id="${wsEscapeHtml(m.id)}" data-tier="${tier}">
        <span class="mk-map-list-item-top">
            <span class="mk-map-list-item-price">${wsEscapeHtml(m.price_label || '—')}</span>
            ${tierLabel ? `<span class="mk-map-list-tier mk-map-list-tier--${tier}">${tierLabel}</span>` : ''}
        </span>
        <span class="mk-map-list-item-title">${wsEscapeHtml(m.title || 'بدون عنوان')}</span>
        <span class="mk-map-list-item-meta">
            ${m.area_label ? `<span>${wsEscapeHtml(m.area_label)}</span>` : ''}
            ${m.rooms ? `<span>${wsEscapeHtml(m.rooms)} خواب</span>` : ''}
            ${loc ? `<span>${wsEscapeHtml(loc)}</span>` : ''}
        </span>
    </button>`;
}

function buildMapLegendScale(mode, stats) {
    const barClass = {
        value: 'price',
        full_deposit: 'full-deposit',
        grid: 'grid',
        heat_density: 'heat-density',
        heat_price: 'heat-price',
        heat_pps: 'heat-pps',
    }[mode] || 'price';

    const labels = {
        value: { low: 'ارزان', high: 'گران' },
        full_deposit: { low: 'رهن کم', high: 'رهن زیاد' },
        grid: { low: 'کم', high: `${stats?.maxCount ?? '…'}` },
        heat_density: { low: 'کم', high: 'زیاد' },
        heat_price: { low: 'ارزان', high: 'گران' },
        heat_pps: { low: 'ارزان/متر', high: 'گران/متر' },
    }[mode] || { low: 'ارزان', high: 'گران' };

    const caption = stats?.rangeText
        ? `<span class="mk-map-legend-caption">${stats.rangeText}</span>`
        : '';

    const inlineStyle = ['heat_density', 'heat_price', 'heat_pps'].includes(mode)
        ? ` style="background:${cssGradientFromStops(mode.replace('heat_', ''))}"`
        : '';

    return `<div class="mk-map-legend-scale mk-map-legend-scale--inline">
        <div class="mk-map-legend-scale-row">
            <span class="mk-map-legend-scale-end">${labels.low}</span>
            <div class="mk-map-legend-scale-track" aria-hidden="true">
                <span class="mk-map-legend-scale-bar mk-map-legend-scale-bar--${barClass}"${inlineStyle}></span>
            </div>
            <span class="mk-map-legend-scale-end">${labels.high}</span>
        </div>
        ${caption}
    </div>`;
}

const MAP_BASEMAP_STORAGE_KEY = 'ws-map-basemap';

const MAP_BASEMAPS = {
    voyager: {
        label: 'شهری',
        hint: 'خیابان‌ها و محله‌ها',
        preview: 'voyager',
        exportSafe: true,
        create() {
            return L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                maxZoom: 20,
                subdomains: 'abcd',
                crossOrigin: true,
            });
        },
    },
    standard: {
        label: 'استاندارد',
        hint: 'OpenStreetMap کلاسیک',
        preview: 'standard',
        exportSafe: false,
        create() {
            return L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
                maxZoom: 19,
                subdomains: 'abc',
                crossOrigin: true,
            });
        },
    },
    light: {
        label: 'روشن',
        hint: 'مینیمال و تمیز',
        preview: 'light',
        exportSafe: true,
        create() {
            return L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; OSM &copy; CARTO',
                maxZoom: 20,
                subdomains: 'abcd',
                crossOrigin: true,
            });
        },
    },
    dark: {
        label: 'تاریک',
        hint: 'مناسب شب و تمرکز',
        preview: 'dark',
        exportSafe: true,
        create() {
            return L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; OSM &copy; CARTO',
                maxZoom: 20,
                subdomains: 'abcd',
                crossOrigin: true,
            });
        },
    },
    satellite: {
        label: 'ماهواره',
        hint: 'تصویر واقعی زمین',
        preview: 'satellite',
        exportSafe: true,
        create() {
            return L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: '&copy; Esri',
                maxZoom: 19,
                crossOrigin: true,
            });
        },
    },
    hybrid: {
        label: 'ترکیبی',
        hint: 'ماهواره + برچسب',
        preview: 'hybrid',
        exportSafe: true,
        create() {
            const group = L.layerGroup();
            group.addLayer(L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19,
                crossOrigin: true,
            }));
            group.addLayer(L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19,
                opacity: 0.88,
                crossOrigin: true,
            }));
            return group;
        },
    },
    topo: {
        label: 'توپوگرافی',
        hint: 'ارتفاع و جغرافیا',
        preview: 'topo',
        exportSafe: true,
        create() {
            return L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OSM &copy; OpenTopoMap',
                maxZoom: 17,
                subdomains: 'abc',
                crossOrigin: true,
            });
        },
    },
};

const MAP_MODE_LABELS = {
    markers: 'نقاط',
    value: 'رنگ قیمت',
    grid: 'شبکه',
    market: 'بازار',
    full_deposit: 'رهن کامل',
    heat_density: 'هیت تراکم',
    heat_price: 'هیت قیمت',
    heat_pps: 'هیت متر',
};

function getDefaultBasemapId() {
    try {
        const stored = localStorage.getItem(MAP_BASEMAP_STORAGE_KEY);
        if (stored && MAP_BASEMAPS[stored]) return stored;
    } catch (e) { /* ignore */ }
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'voyager';
}

function waitForMapTiles(map, timeoutMs = 4000) {
    return new Promise((resolve) => {
        const imgs = map.getContainer().querySelectorAll('img.leaflet-tile');
        let pending = 0;
        imgs.forEach((img) => {
            if (!img.complete) {
                pending += 1;
                const done = () => {
                    pending -= 1;
                    if (pending <= 0) resolve();
                };
                img.addEventListener('load', done, { once: true });
                img.addEventListener('error', done, { once: true });
            }
        });
        if (pending === 0) {
            setTimeout(resolve, 280);
        } else {
            setTimeout(resolve, timeoutMs);
        }
    });
}

function showMapExportToast(message, type = 'info') {
    const toast = document.getElementById('mkMapExportToast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `mk-map-export-toast mk-map-export-toast--${type}`;
    toast.hidden = false;
    clearTimeout(showMapExportToast._timer);
    showMapExportToast._timer = setTimeout(() => { toast.hidden = true; }, 4200);
}

async function captureMapScreenshot(map, meta = {}) {
    if (typeof html2canvas !== 'function') {
        showMapExportToast('ابزار ذخیره تصویر بارگذاری نشده است', 'error');
        return;
    }

    const exportBtn = document.getElementById('mkMapExportBtn');
    const stage = document.querySelector('.mk-map-stage');
    exportBtn?.classList.add('is-loading');
    stage?.classList.add('mk-map-capturing');
    map.closePopup();

    try {
        await waitForMapTiles(map);
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

        const container = map.getContainer();
        const scale = Math.min(2.5, Math.max(1.5, window.devicePixelRatio || 1.5));
        const shot = await html2canvas(container, {
            useCORS: true,
            allowTaint: false,
            logging: false,
            scale,
            backgroundColor: '#e8edf2',
            ignoreElements: (el) => el.classList?.contains('leaflet-control-container'),
        });

        const footerH = Math.round(44 * scale);
        const finalCanvas = document.createElement('canvas');
        finalCanvas.width = shot.width;
        finalCanvas.height = shot.height + footerH;
        const ctx = finalCanvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, finalCanvas.width, finalCanvas.height);
        ctx.drawImage(shot, 0, 0);

        const pad = 14 * scale;
        const modeLabel = MAP_MODE_LABELS[meta.activeMode] || 'نقاط';
        const title = meta.datasetName || 'نقشه آگهی‌ها';
        const city = meta.datasetCity ? ` · ${meta.datasetCity}` : '';
        const zoom = map.getZoom();
        const date = wsFormatJalaliToday();
        ctx.fillStyle = '#0f172a';
        ctx.font = `700 ${13 * scale}px Vazirmatn, Tahoma, sans-serif`;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText(`${title}${city}`, finalCanvas.width - pad, shot.height + 10 * scale);
        ctx.fillStyle = '#64748b';
        ctx.font = `500 ${11 * scale}px Vazirmatn, Tahoma, sans-serif`;
        ctx.fillText(`حالت: ${modeLabel} · زوم ${zoom.toLocaleString('fa-IR')} · ${date}`, finalCanvas.width - pad, shot.height + 26 * scale);

        const link = document.createElement('a');
        const safeName = String(title).replace(/[^\w\u0600-\u06FF\-]+/g, '_').slice(0, 40);
        link.download = `map-${safeName}-z${zoom}-${new Date().toISOString().slice(0, 10)}.png`;
        link.href = finalCanvas.toDataURL('image/png', 0.95);
        link.click();
        showMapExportToast('تصویر نقشه ذخیره شد', 'success');
    } catch (err) {
        console.error('Map export failed:', err);
        showMapExportToast('ذخیره تصویر ناموفق بود — نوع نقشه را به «شهری» تغییر دهید و دوباره تلاش کنید', 'error');
    } finally {
        exportBtn?.classList.remove('is-loading');
        stage?.classList.remove('mk-map-capturing');
    }
}

function buildBasemapChipHtml(id, cfg, active) {
    return `<button type="button" class="mk-map-basemap-chip${active ? ' is-active' : ''}"
        data-basemap="${wsEscapeHtml(id)}" aria-pressed="${active ? 'true' : 'false'}"
        title="${wsEscapeHtml(cfg.hint)}">
        <span class="mk-map-basemap-preview mk-map-basemap-preview--${cfg.preview}" aria-hidden="true"></span>
        <span class="mk-map-basemap-chip-label">${wsEscapeHtml(cfg.label)}</span>
    </button>`;
}

function setupMapProUI(map, options = {}) {
    const {
        fullBounds,
        focusMaxZoom = 17,
        settings = {},
        getActiveMode = () => 'markers',
    } = options;

    let currentBasemapId = getDefaultBasemapId();
    let currentBasemapLayer = MAP_BASEMAPS[currentBasemapId].create();
    currentBasemapLayer.addTo(map);
    setupMapVpnTip(currentBasemapLayer);

    const basemapBar = document.getElementById('mkMapBasemapBar');
    const basemapMenu = document.getElementById('mkMapBasemapMenu');
    const basemapToggle = document.getElementById('mkMapBasemapToggle');
    const basemapPanel = document.getElementById('mkMapBasemapPanel');
    const zoomBadge = document.getElementById('mkMapZoomBadge');
    const coordsBadge = document.getElementById('mkMapCoordsBadge');
    const exportBtn = document.getElementById('mkMapExportBtn');
    const fitBtn = document.getElementById('mkMapFitBtn');
    const fullscreenBtn = document.getElementById('mkMapFullscreenBtn');
    const stage = document.querySelector('.mk-map-stage');
    const panel = document.querySelector('.mk-map-panel');

    function setBasemapMenuOpen(open) {
        if (!basemapMenu) return;
        if (open) {
            basemapMenu.removeAttribute('hidden');
            basemapToggle?.setAttribute('aria-expanded', 'true');
            basemapPanel?.classList.add('is-open');
        } else {
            basemapMenu.setAttribute('hidden', '');
            basemapToggle?.setAttribute('aria-expanded', 'false');
            basemapPanel?.classList.remove('is-open');
        }
    }

    function updateBasemapUI(activeId) {
        document.querySelectorAll('.mk-map-basemap-chip, .mk-map-basemap-option').forEach((btn) => {
            const on = btn.dataset.basemap === activeId;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        if (basemapToggle) {
            const cfg = MAP_BASEMAPS[activeId];
            basemapToggle.title = `نوع نقشه: ${cfg?.label || ''}`;
        }
    }

    function bindBasemapButtons(container) {
        if (!container) return;
        container.querySelectorAll('[data-basemap]').forEach((btn) => {
            btn.addEventListener('click', () => setBasemap(btn.dataset.basemap));
        });
    }

    function renderBasemapBar() {
        const html = Object.entries(MAP_BASEMAPS)
            .map(([id, cfg]) => buildBasemapChipHtml(id, cfg, id === currentBasemapId))
            .join('');
        if (basemapBar) {
            basemapBar.innerHTML = html;
            bindBasemapButtons(basemapBar);
        }
        if (basemapMenu) {
            basemapMenu.innerHTML = Object.entries(MAP_BASEMAPS).map(([id, cfg]) => `
                <button type="button" class="mk-map-basemap-option${id === currentBasemapId ? ' is-active' : ''}"
                    data-basemap="${id}" aria-pressed="${id === currentBasemapId ? 'true' : 'false'}"
                    title="${wsEscapeHtml(cfg.hint)}">
                    <span class="mk-map-basemap-preview mk-map-basemap-preview--${cfg.preview}" aria-hidden="true"></span>
                    <span class="mk-map-basemap-option-text">
                        <strong>${wsEscapeHtml(cfg.label)}</strong>
                        <span>${wsEscapeHtml(cfg.hint)}</span>
                    </span>
                </button>
            `).join('');
            bindBasemapButtons(basemapMenu);
        }
        updateBasemapUI(currentBasemapId);
    }

    function setBasemap(id) {
        const cfg = MAP_BASEMAPS[id];
        if (!cfg || id === currentBasemapId) return;
        map.removeLayer(currentBasemapLayer);
        currentBasemapId = id;
        currentBasemapLayer = cfg.create();
        currentBasemapLayer.addTo(map);
        setupMapVpnTip(currentBasemapLayer);
        try { localStorage.setItem(MAP_BASEMAP_STORAGE_KEY, id); } catch (e) { /* ignore */ }
        updateBasemapUI(id);
        setBasemapMenuOpen(false);
    }

    renderBasemapBar();

    basemapToggle?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!basemapMenu) return;
        setBasemapMenuOpen(basemapMenu.hasAttribute('hidden'));
    });

    document.addEventListener('click', (e) => {
        if (!basemapMenu || basemapMenu.hasAttribute('hidden')) return;
        if (e.target.closest('#mkMapBasemapPanel')) return;
        setBasemapMenuOpen(false);
    });

    L.control.scale({ imperial: false, metric: true, position: 'bottomright' }).addTo(map);

    function updateZoomBadge() {
        if (!zoomBadge) return;
        const z = map.getZoom();
        zoomBadge.textContent = (z != null && !Number.isNaN(z))
            ? `زوم ${z.toLocaleString('fa-IR')}`
            : 'زوم —';
    }

    map.on('zoomend', updateZoomBadge);

    map.on('mousemove', (e) => {
        if (coordsBadge) {
            coordsBadge.textContent = `${e.latlng.lat.toFixed(4)}° , ${e.latlng.lng.toFixed(4)}°`;
        }
    });

    fitBtn?.addEventListener('click', () => {
        if (!fullBounds?.isValid()) return;
        map.fitBounds(fullBounds, { padding: [56, 56], maxZoom: focusMaxZoom, animate: true });
    });

    fullscreenBtn?.addEventListener('click', async () => {
        const target = panel || stage;
        if (!target) return;
        try {
            if (!document.fullscreenElement) {
                await target.requestFullscreen();
                fullscreenBtn.querySelector('i')?.classList.replace('fa-expand', 'fa-compress');
            } else {
                await document.exitFullscreen();
                fullscreenBtn.querySelector('i')?.classList.replace('fa-compress', 'fa-expand');
            }
        } catch (e) { /* ignore */ }
    });

    document.addEventListener('fullscreenchange', () => {
        if (!document.fullscreenElement) {
            fullscreenBtn?.querySelector('i')?.classList.replace('fa-compress', 'fa-expand');
        }
        setTimeout(() => map.invalidateSize(), 120);
    });

    exportBtn?.addEventListener('click', () => {
        captureMapScreenshot(map, {
            datasetName: settings.datasetName,
            datasetCity: settings.datasetCity,
            activeMode: getActiveMode(),
        });
    });

    updateBasemapUI(currentBasemapId);

    return { setBasemap, getBasemapId: () => currentBasemapId, updateZoomBadge };
}

function initMap(allMarkers, settings) {
    if (!allMarkers || !allMarkers.length || !window.L) return;
    const el = document.getElementById('wsMap');
    if (!el) return;

    const focusMaxZoom = settings?.focusMaxZoom ?? 17;
    const clusterDisableZoom = settings?.clusterDisableZoom ?? 15;
    const mapModesEnabled = settings?.mapModes !== false && allMarkers.length > 1;
    const popupOpts = {
        className: 'mk-map-popup-shell',
        maxWidth: 300,
        minWidth: 260,
    };

    const map = L.map('wsMap', {
        zoomControl: false,
        scrollWheelZoom: true,
    });
    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    const fullBounds = L.latLngBounds();
    allMarkers.forEach(m => fullBounds.extend([m.lat, m.lng]));

    const useCluster = settings?.map_cluster !== false && window.L.markerClusterGroup;

    let sellerFilter = 'all';
    const heatLayerReady = !!window.L;
    let activeMode = settings?.map_heatmap && heatLayerReady ? 'heat_density' : 'markers';
    let showRings = false;
    let layers = {};
    let layerStats = {};
    let markerRegistry = {};
    let highlightedMarkerId = null;
    let selectedMarkerId = null;
    const filterState = {
        txMode: 'all',
        neighborhood: '',
        priceMin: '',
        priceMax: '',
        depositMin: '',
        depositMax: '',
        rentMin: '',
        rentMax: '',
        areaMin: '',
        areaMax: '',
        rooms: 'all',
        yearMin: '',
        yearMax: '',
        freshness: 'all',
        valueTier: 'all',
        elevator: false,
        parking: false,
        storage: false,
    };
    const filterBounds = computeMapFilterBounds(allMarkers, settings);

    const mapPro = setupMapProUI(map, {
        fullBounds,
        focusMaxZoom,
        settings,
        getActiveMode: () => activeMode,
    });

    function getFilteredMarkers() {
        return applyMapMarkerFilters(allMarkers, filterState, sellerFilter);
    }

    function syncMarkerRegistry() {
        markerRegistry = layers[activeMode]?._registry || {};
    }

    function registerMarker(marker, m, registry) {
        if (m.id != null) registry[m.id] = { marker, data: m };
        return marker;
    }

    function markerColorMode() {
        if (activeMode === 'market') return 'market';
        if (activeMode === 'value' || activeMode === 'full_deposit') return 'value';
        return 'seller';
    }

    function buildPinIcon(m, { selected = false, colorMode = null } = {}) {
        const mode = colorMode || markerColorMode();
        let pinClass = 'mk-map-pin';
        if (mode === 'market') {
            const tier = m.market_tier || 'unknown';
            pinClass = `mk-map-pin mk-map-pin--market mk-map-pin--${tier}`;
            if (m.is_consultant || m.is_disguised) pinClass += ' mk-map-pin--consultant-ring';
        } else if (mode === 'value') {
            const tier = m._valueTier ?? 0;
            const bg = valueTierColor(tier);
            pinClass = 'mk-map-pin mk-map-pin--value';
            if (selected) pinClass += ' mk-map-pin--selected';
            if (selected) {
                return L.divIcon({
                    className: 'mk-map-pin-wrap mk-map-pin-wrap--selected',
                    html: `<div class="${pinClass}" style="background:${bg}"><i class="fas fa-location-dot" aria-hidden="true"></i></div>`,
                    iconSize: [28, 28],
                    iconAnchor: [14, 26],
                });
            }
            return L.divIcon({
                className: 'mk-map-pin-wrap',
                html: `<div class="${pinClass}" style="background:${bg}"></div>`,
                iconSize: [18, 18],
                iconAnchor: [9, 9],
            });
        } else {
            pinClass += ` mk-map-pin--${mapSellerKind(m)}`;
        }
        if (selected) pinClass += ' mk-map-pin--selected';

        if (selected) {
            return L.divIcon({
                className: 'mk-map-pin-wrap mk-map-pin-wrap--selected',
                html: `<div class="${pinClass}"><i class="fas fa-location-dot" aria-hidden="true"></i></div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 26],
            });
        }
        return L.divIcon({
            className: 'mk-map-pin-wrap',
            html: `<div class="${pinClass}"></div>`,
            iconSize: [18, 18],
            iconAnchor: [9, 9],
        });
    }

    function selectMarker(id) {
        const layerColorMode = layers[activeMode]?._colorMode || markerColorMode();
        const isCircleLayer = layers[activeMode]?._isValueLayer;

        if (selectedMarkerId != null && selectedMarkerId !== id) {
            const prev = markerRegistry[selectedMarkerId];
            if (prev?.marker) {
                if (isCircleLayer && prev.marker._mkCircleStyle) {
                    prev.marker.setStyle(prev.marker._mkCircleStyle({ selected: false }));
                } else {
                    prev.marker.setIcon(buildPinIcon(prev.data, { colorMode: layerColorMode }));
                }
                prev.marker.setZIndexOffset(0);
            }
        }
        selectedMarkerId = id;
        const entry = markerRegistry[id];
        if (entry?.marker) {
            if (isCircleLayer && entry.marker._mkCircleStyle) {
                entry.marker.setStyle(entry.marker._mkCircleStyle({ selected: true }));
            } else {
                entry.marker.setIcon(buildPinIcon(entry.data, { selected: true, colorMode: layerColorMode }));
            }
            entry.marker.setZIndexOffset(1200);
        }
        document.querySelectorAll('.mk-map-list-item').forEach((btn) => {
            btn.classList.toggle('is-selected', parseInt(btn.dataset.id, 10) === id);
        });
    }

    function highlightMarker(id, on) {
        const entry = markerRegistry[id];
        if (!entry) return;
        if (id === selectedMarkerId) return;
        if (entry.marker._mkCircleStyle) {
            entry.marker.setStyle(entry.marker._mkCircleStyle({ highlighted: !!on }));
            return;
        }
        const el = entry.marker.getElement?.();
        if (!el) return;
        el.classList.toggle('mk-map-pin-wrap--highlight', !!on);
    }

    function focusMarkerFromList(m) {
        if (!m) return;
        const entry = markerRegistry[m.id];
        if (!entry && activeMode.startsWith('heat_')) {
            map.flyTo([m.lat, m.lng], Math.min(19, focusMaxZoom + 1), { duration: 0.5 });
            return;
        }
        if (!entry) return;

        highlightedMarkerId = m.id;
        const targetZoom = Math.min(19, focusMaxZoom + 1);
        const clusterGroup = layers[activeMode]?._clusterGroup;

        const finish = () => {
            selectMarker(m.id);
            if (map.getZoom() < targetZoom) {
                map.setView([m.lat, m.lng], targetZoom, { animate: true });
                map.once('moveend', () => entry.marker.openPopup?.(), { once: true });
            } else {
                map.panTo([m.lat, m.lng], { animate: true });
                setTimeout(() => entry.marker.openPopup?.(), 200);
            }
            const listItem = document.querySelector(`.mk-map-list-item[data-id="${m.id}"]`);
            listItem?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        };

        if (clusterGroup && ['markers', 'market', 'value', 'full_deposit'].includes(activeMode)) {
            clusterGroup.zoomToShowLayer(entry.marker, finish);
        } else {
            map.flyTo([m.lat, m.lng], targetZoom, { duration: 0.5 });
            map.once('moveend', finish, { once: true });
        }
    }

    function flyToMarker(m) {
        if (!m) return;
        map.flyTo([m.lat, m.lng], Math.max(map.getZoom(), focusMaxZoom - 1), { duration: 0.45 });
        const entry = markerRegistry[m.id];
        if (entry?.marker?.openPopup) {
            setTimeout(() => entry.marker.openPopup(), 380);
        }
    }

    function percentileIntensity(values, index) {
        const positives = values.filter(v => v > 0).sort((a, b) => a - b);
        const v = values[index];
        if (!positives.length || !v) return 0.1;
        const rank = positives.findIndex(x => x >= v);
        const pct = rank / Math.max(positives.length - 1, 1);
        return 0.12 + pct * 0.88;
    }

    function gridFillColor(t) {
        return heatColorAt(t, 'density');
    }

    function buildHeatLayer(source, { palette = 'density', valueKey = null, perSqm = false } = {}) {
        const emptyLayer = L.layerGroup();
        if (!source.length) return { layer: emptyLayer, stats: {} };
        if (!window.L) {
            return {
                layer: emptyLayer,
                stats: { rangeText: 'نقشه بارگذاری نشده — صفحه را رفرش کنید' },
            };
        }

        const weighted = palette !== 'density';
        const values = weighted
            ? source.map(m => Number(m[valueKey] || m.filter_value || m.price || 0) || 0)
            : [];
        const intensities = weighted ? normalizeHeatValues(values) : null;
        const positives = weighted ? values.filter(v => v > 0) : [];
        const minVal = positives.length ? Math.min(...positives) : 0;
        const maxVal = positives.length ? Math.max(...positives) : 0;

        const heatData = source.map((m, i) => {
            let intensity = weighted ? intensities[i] : 1.0;
            if (!weighted) {
                intensity = Math.min(2.5, 1.2 + 30 / Math.max(source.length, 1));
            }
            return [m.lat, m.lng, intensity];
        });

        const heatOpts = computeHeatLayerOptions(source, palette, map, { weighted });
        const layer = createMkHeatLayer(heatData, map, {
            palette,
            weighted,
            source,
            radius: heatOpts.radius,
        });

        let rangeText = '';
        if (palette === 'density') {
            rangeText = `${source.length.toLocaleString('fa-IR')} نقطه — هاله گرم‌تر = تراکم بیشتر`;
        } else if (minVal && maxVal) {
            rangeText = `از ${formatMapMoney(minVal, perSqm)} تا ${formatMapMoney(maxVal, perSqm)}`;
        } else {
            rangeText = 'داده کافی برای وزن‌دهی نیست';
        }

        return {
            layer,
            stats: { rangeText, minVal, maxVal },
        };
    }

    function buildMarkerLayer(source, { colorMode = 'seller' } = {}) {
        const localRegistry = {};
        const wrapper = L.layerGroup();
        const rings = L.layerGroup();
        let clusterGroup = null;
        const group = useCluster
            ? (clusterGroup = L.markerClusterGroup({
                disableClusteringAtZoom: clusterDisableZoom,
                maxClusterRadius: 26,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false,
                animateAddingMarkers: false,
                iconCreateFunction(cluster) {
                    const count = cluster.getChildCount();
                    let size = 'mk-map-cluster--md';
                    if (count < 12) size = 'mk-map-cluster--sm';
                    else if (count > 60) size = 'mk-map-cluster--lg';
                    return L.divIcon({
                        html: `<div class="mk-map-cluster ${size}"><span>${count}</span></div>`,
                        className: 'mk-map-cluster-wrap',
                        iconSize: [48, 48],
                    });
                },
            }))
            : L.layerGroup();

        source.forEach((m) => {
            addAccuracyRings(rings, m, showRings);
            const isSelected = m.id === selectedMarkerId;
            const icon = buildPinIcon(m, { selected: isSelected, colorMode });
            const marker = registerMarker(L.marker([m.lat, m.lng], { icon }), m, localRegistry);
            if (isSelected) marker.setZIndexOffset(1200);
            marker.bindPopup(buildMapMarkerPopup(m), popupOpts);
            marker.on('click', () => selectMarker(m.id));
            marker.on('mouseover', () => highlightMarker(m.id, true));
            marker.on('mouseout', () => {
                if (highlightedMarkerId !== m.id && m.id !== selectedMarkerId) highlightMarker(m.id, false);
            });
            group.addLayer(marker);
        });
        wrapper.addLayer(rings);
        wrapper.addLayer(group);
        wrapper._clusterGroup = clusterGroup;
        wrapper._colorMode = colorMode;
        wrapper._registry = localRegistry;
        return wrapper;
    }

    function enrichWithValueTier(source, valueKey = 'filter_value') {
        const values = source.map(m => Number(m[valueKey] || m.filter_value || m.price || 0) || 0);
        return source.map((m, i) => {
            const v = values[i];
            let tier = 0;
            if (v > 0 && values.some(x => x > 0)) {
                tier = Math.min(5, Math.max(1, Math.ceil(percentileIntensity(values, i) * 5)));
            }
            return { ...m, _valueTier: tier };
        });
    }

    function valueCircleStyle(m, { selected = false, highlighted = false } = {}) {
        const color = valueTierColor(m._valueTier ?? 0);
        return {
            radius: selected ? 12 : (highlighted ? 11 : 9),
            fillColor: color,
            fillOpacity: selected ? 0.95 : 0.85,
            color: selected ? '#0f172a' : '#ffffff',
            weight: selected ? 2.5 : 2,
            opacity: 1,
        };
    }

    function buildValueMarkerLayer(source, { valueKey = 'filter_value', perSqm = false } = {}) {
        const enriched = enrichWithValueTier(source, valueKey);
        const values = enriched.map(m => Number(m[valueKey] || m.filter_value || m.price || 0) || 0);
        const positives = values.filter(v => v > 0);
        const minVal = positives.length ? Math.min(...positives) : 0;
        const maxVal = positives.length ? Math.max(...positives) : 0;

        const localRegistry = {};
        const wrapper = L.layerGroup();
        const rings = L.layerGroup();
        let clusterGroup = null;
        const group = useCluster
            ? (clusterGroup = L.markerClusterGroup({
                disableClusteringAtZoom: clusterDisableZoom,
                maxClusterRadius: 26,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false,
                animateAddingMarkers: false,
                iconCreateFunction(cluster) {
                    const count = cluster.getChildCount();
                    let size = 'mk-map-cluster--md';
                    if (count < 12) size = 'mk-map-cluster--sm';
                    else if (count > 60) size = 'mk-map-cluster--lg';
                    return L.divIcon({
                        html: `<div class="mk-map-cluster ${size}"><span>${count}</span></div>`,
                        className: 'mk-map-cluster-wrap',
                        iconSize: [48, 48],
                    });
                },
            }))
            : L.layerGroup();

        enriched.forEach((m) => {
            addAccuracyRings(rings, m, showRings);
            const isSelected = m.id === selectedMarkerId;
            const marker = L.circleMarker([m.lat, m.lng], valueCircleStyle(m, { selected: isSelected }));
            marker._mkCircleStyle = (opts = {}) => valueCircleStyle(m, opts);
            registerMarker(marker, m, localRegistry);
            if (isSelected) marker.setZIndexOffset(1200);
            marker.bindPopup(buildMapMarkerPopup(m), popupOpts);
            marker.on('click', () => selectMarker(m.id));
            marker.on('mouseover', () => highlightMarker(m.id, true));
            marker.on('mouseout', () => {
                if (highlightedMarkerId !== m.id && m.id !== selectedMarkerId) highlightMarker(m.id, false);
            });
            group.addLayer(marker);
        });

        wrapper.addLayer(rings);
        wrapper.addLayer(group);
        wrapper._clusterGroup = clusterGroup;
        wrapper._colorMode = 'value';
        wrapper._isValueLayer = true;
        wrapper._registry = localRegistry;

        return {
            layer: wrapper,
            stats: {
                rangeText: minVal && maxVal
                    ? `از ${formatMapMoney(minVal, perSqm)} تا ${formatMapMoney(maxVal, perSqm)}`
                    : 'داده کافی برای رنگ‌بندی نیست',
            },
        };
    }

    function buildGridLayer(source) {
        const layer = L.layerGroup();
        if (!source.length) return { layer, stats: {} };

        const bounds = L.latLngBounds(source.map(m => [m.lat, m.lng]));
        const sw = bounds.getSouthWest();
        const ne = bounds.getNorthEast();
        const latSpan = ne.lat - sw.lat || 0.01;
        const lngSpan = ne.lng - sw.lng || 0.01;
        const gridSize = Math.min(18, Math.max(8, Math.round(Math.sqrt(source.length / 2))));

        const cells = {};
        source.forEach(m => {
            const i = Math.min(gridSize - 1, Math.floor(((m.lat - sw.lat) / latSpan) * gridSize));
            const j = Math.min(gridSize - 1, Math.floor(((m.lng - sw.lng) / lngSpan) * gridSize));
            const key = `${i}_${j}`;
            if (!cells[key]) cells[key] = { count: 0, i, j, markers: [] };
            cells[key].count += 1;
            cells[key].markers.push(m);
        });

        const maxCount = Math.max(...Object.values(cells).map(c => c.count), 1);
        const latStep = latSpan / gridSize;
        const lngStep = lngSpan / gridSize;
        const inset = 0.12;

        Object.values(cells).forEach(cell => {
            const intensity = cell.count / maxCount;
            const lat1 = sw.lat + cell.i * latStep + latStep * inset;
            const lat2 = sw.lat + (cell.i + 1) * latStep - latStep * inset;
            const lng1 = sw.lng + cell.j * lngStep + lngStep * inset;
            const lng2 = sw.lng + (cell.j + 1) * lngStep - lngStep * inset;
            const rect = L.rectangle([[lat1, lng1], [lat2, lng2]], {
                fillColor: gridFillColor(intensity),
                fillOpacity: 0.26 + intensity * 0.54,
                color: gridFillColor(intensity),
                weight: 1.25,
                opacity: 0.42 + intensity * 0.38,
            });
            const sample = cell.markers[0];
            if (sample) rect.bindPopup(buildMapMarkerPopup(sample), popupOpts);
            layer.addLayer(rect);

            if (cell.count >= 2) {
                const centerLat = (lat1 + lat2) / 2;
                const centerLng = (lng1 + lng2) / 2;
                const label = L.marker([centerLat, centerLng], {
                    icon: L.divIcon({
                        className: 'mk-map-grid-label-wrap',
                        html: `<span class="mk-map-grid-label">${cell.count.toLocaleString('fa-IR')}</span>`,
                        iconSize: [28, 28],
                        iconAnchor: [14, 14],
                    }),
                    interactive: false,
                });
                layer.addLayer(label);
            }
        });

        return {
            layer,
            stats: {
                maxCount,
                rangeText: 'هر خانه = تعداد آگهی در آن محدوده',
            },
        };
    }

    function buildLayers() {
        const visible = getFilteredMarkers();
        const value = buildValueMarkerLayer(visible);
        const fullDeposit = buildValueMarkerLayer(visible, { valueKey: 'full_deposit' });
        const grid = buildGridLayer(visible);
        const heatDensity = buildHeatLayer(visible, { palette: 'density' });
        const heatPrice = buildHeatLayer(visible, { palette: 'price', valueKey: 'filter_value' });
        const heatPps = buildHeatLayer(visible, { palette: 'pps', valueKey: 'pps', perSqm: true });

        layerStats = {
            value: value.stats,
            full_deposit: fullDeposit.stats,
            grid: grid.stats,
            heat_density: heatDensity.stats,
            heat_price: heatPrice.stats,
            heat_pps: heatPps.stats,
            market: {
                under: visible.filter(m => m.market_tier === 'under').length,
                fair: visible.filter(m => m.market_tier === 'fair').length,
                over: visible.filter(m => m.market_tier === 'over').length,
            },
        };

        return {
            markers: buildMarkerLayer(visible, { colorMode: 'seller' }),
            market: buildMarkerLayer(visible, { colorMode: 'market' }),
            value: value.layer,
            full_deposit: fullDeposit.layer,
            grid: grid.layer,
            heat_density: heatDensity.layer,
            heat_price: heatPrice.layer,
            heat_pps: heatPps.layer,
            _count: visible.length,
            _visible: visible,
        };
    }

    function refreshListPanel() {
        const listBody = document.getElementById('mkMapListBody');
        const listCount = document.getElementById('mkMapListCount');
        const listPanel = document.getElementById('mkMapList');
        if (!listBody || !listPanel || listPanel.hidden) return;

        const visible = layers._visible || getFilteredMarkers();
        const bounds = map.getBounds();
        const inView = visible.filter(m => bounds.contains([m.lat, m.lng]));
        const sorted = [...inView].sort((a, b) => {
            const sa = a.value_score ?? 999;
            const sb = b.value_score ?? 999;
            return sa - sb;
        });

        if (listCount) {
            listCount.textContent = `${sorted.length.toLocaleString('fa-IR')} مورد در نما`;
        }
        listBody.innerHTML = sorted.length
            ? sorted.map(buildMapListItemHtml).join('')
            : '<p class="mk-map-list-empty">فایلی در این نما نیست — زوم یا فیلتر را تغییر دهید.</p>';

        listBody.querySelectorAll('.mk-map-list-item').forEach((btn) => {
            btn.addEventListener('click', () => {
                const id = parseInt(btn.dataset.id, 10);
                const m = (layers._visible || getFilteredMarkers()).find(x => x.id === id);
                focusMarkerFromList(m);
            });
            btn.addEventListener('mouseenter', () => highlightMarker(parseInt(btn.dataset.id, 10), true));
            btn.addEventListener('mouseleave', () => {
                const id = parseInt(btn.dataset.id, 10);
                if (highlightedMarkerId !== id && id !== selectedMarkerId) highlightMarker(id, false);
            });
        });
        if (selectedMarkerId != null) {
            listBody.querySelectorAll('.mk-map-list-item').forEach((btn) => {
                btn.classList.toggle('is-selected', parseInt(btn.dataset.id, 10) === selectedMarkerId);
            });
        }
    }

    function updateFilterBadge() {
        const badge = document.getElementById('mkMapFilterBadge');
        const n = countActiveMapFilters(filterState) + (showRings === false ? 0 : 0);
        const total = countActiveMapFilters(filterState);
        if (!badge) return;
        if (total > 0) {
            badge.hidden = false;
            badge.textContent = total.toLocaleString('fa-IR');
        } else {
            badge.hidden = true;
        }
    }

    function syncFilterInputs() {
        const priceMinEl = document.getElementById('mkMapPriceMin');
        const priceMaxEl = document.getElementById('mkMapPriceMax');
        const depositMinEl = document.getElementById('mkMapDepositMin');
        const depositMaxEl = document.getElementById('mkMapDepositMax');
        const rentMinEl = document.getElementById('mkMapRentMin');
        const rentMaxEl = document.getElementById('mkMapRentMax');
        const areaMinEl = document.getElementById('mkMapAreaMin');
        const areaMaxEl = document.getElementById('mkMapAreaMax');
        const roomsEl = document.getElementById('mkMapRooms');
        const yearMinEl = document.getElementById('mkMapYearMin');
        const yearMaxEl = document.getElementById('mkMapYearMax');
        const freshEl = document.getElementById('mkMapFreshness');
        const valueTierEl = document.getElementById('mkMapValueTier');
        const txModeEl = document.getElementById('mkMapTxMode');
        const neighborhoodEl = document.getElementById('mkMapNeighborhood');
        const elevatorEl = document.getElementById('mkMapElevator');
        const parkingEl = document.getElementById('mkMapParking');
        const storageEl = document.getElementById('mkMapStorage');
        const ringsEl = document.getElementById('mkMapShowRings');
        const setNum = (el, val) => {
            if (!el) return;
            el.value = val ? formatWithSeparators(val) : '';
            el.dataset.rawValue = val ? String(val) : '';
        };
        setNum(priceMinEl, filterState.priceMin);
        setNum(priceMaxEl, filterState.priceMax);
        setNum(depositMinEl, filterState.depositMin);
        setNum(depositMaxEl, filterState.depositMax);
        setNum(rentMinEl, filterState.rentMin);
        setNum(rentMaxEl, filterState.rentMax);
        setNum(areaMinEl, filterState.areaMin);
        setNum(areaMaxEl, filterState.areaMax);
        setNum(yearMinEl, filterState.yearMin);
        setNum(yearMaxEl, filterState.yearMax);
        if (roomsEl) roomsEl.value = filterState.rooms;
        if (freshEl) freshEl.value = filterState.freshness;
        if (valueTierEl) valueTierEl.value = filterState.valueTier;
        if (txModeEl) txModeEl.value = filterState.txMode;
        if (neighborhoodEl) neighborhoodEl.value = filterState.neighborhood || '';
        if (elevatorEl) elevatorEl.checked = filterState.elevator;
        if (parkingEl) parkingEl.checked = filterState.parking;
        if (storageEl) storageEl.checked = filterState.storage;
        if (ringsEl) ringsEl.checked = showRings;
        updateFilterBadge();
    }

    function applyAdvancedFilters() {
        const priceMinEl = document.getElementById('mkMapPriceMin');
        const priceMaxEl = document.getElementById('mkMapPriceMax');
        const depositMinEl = document.getElementById('mkMapDepositMin');
        const depositMaxEl = document.getElementById('mkMapDepositMax');
        const rentMinEl = document.getElementById('mkMapRentMin');
        const rentMaxEl = document.getElementById('mkMapRentMax');
        const areaMinEl = document.getElementById('mkMapAreaMin');
        const areaMaxEl = document.getElementById('mkMapAreaMax');
        const roomsEl = document.getElementById('mkMapRooms');
        const yearMinEl = document.getElementById('mkMapYearMin');
        const yearMaxEl = document.getElementById('mkMapYearMax');
        const freshEl = document.getElementById('mkMapFreshness');
        const valueTierEl = document.getElementById('mkMapValueTier');
        const txModeEl = document.getElementById('mkMapTxMode');
        const neighborhoodEl = document.getElementById('mkMapNeighborhood');
        const elevatorEl = document.getElementById('mkMapElevator');
        const parkingEl = document.getElementById('mkMapParking');
        const storageEl = document.getElementById('mkMapStorage');
        const ringsEl = document.getElementById('mkMapShowRings');
        filterState.txMode = txModeEl?.value || 'all';
        filterState.neighborhood = neighborhoodEl?.value || '';
        filterState.priceMin = readFormattedInput(priceMinEl);
        filterState.priceMax = readFormattedInput(priceMaxEl);
        filterState.depositMin = readFormattedInput(depositMinEl);
        filterState.depositMax = readFormattedInput(depositMaxEl);
        filterState.rentMin = readFormattedInput(rentMinEl);
        filterState.rentMax = readFormattedInput(rentMaxEl);
        filterState.areaMin = readFormattedInput(areaMinEl);
        filterState.areaMax = readFormattedInput(areaMaxEl);
        filterState.rooms = roomsEl?.value || 'all';
        filterState.yearMin = readFormattedInput(yearMinEl);
        filterState.yearMax = readFormattedInput(yearMaxEl);
        filterState.freshness = freshEl?.value || 'all';
        filterState.valueTier = valueTierEl?.value || 'all';
        filterState.elevator = !!elevatorEl?.checked;
        filterState.parking = !!parkingEl?.checked;
        filterState.storage = !!storageEl?.checked;
        showRings = ringsEl ? ringsEl.checked : false;
        updateFilterBadge();
        refreshLayers();
    }

    function resetAdvancedFilters() {
        filterState.txMode = 'all';
        filterState.neighborhood = '';
        filterState.priceMin = '';
        filterState.priceMax = '';
        filterState.depositMin = '';
        filterState.depositMax = '';
        filterState.rentMin = '';
        filterState.rentMax = '';
        filterState.areaMin = '';
        filterState.areaMax = '';
        filterState.rooms = 'all';
        filterState.yearMin = '';
        filterState.yearMax = '';
        filterState.freshness = 'all';
        filterState.valueTier = 'all';
        filterState.elevator = false;
        filterState.parking = false;
        filterState.storage = false;
        showRings = false;
        syncFilterInputs();
        refreshLayers();
    }

    function setupAdvancedFilters() {
        const toggle = document.getElementById('mkMapFilterToggle');
        const panel = document.getElementById('mkMapAdvancedFilters');
        const resetBtn = document.getElementById('mkMapFilterReset');
        const priceMinLabel = document.getElementById('mkMapPriceMinLabel');
        const priceMaxLabel = document.getElementById('mkMapPriceMaxLabel');
        const label = filterBounds.priceLabel || 'قیمت';
        if (priceMinLabel) priceMinLabel.innerHTML = `حداقل ${label} <small>(میلیون)</small>`;
        if (priceMaxLabel) priceMaxLabel.innerHTML = `حداکثر ${label} <small>(میلیون)</small>`;

        const priceMinEl = document.getElementById('mkMapPriceMin');
        const priceMaxEl = document.getElementById('mkMapPriceMax');
        const areaMinEl = document.getElementById('mkMapAreaMin');
        const areaMaxEl = document.getElementById('mkMapAreaMax');
        if (priceMinEl && filterBounds.priceMin) priceMinEl.placeholder = formatMapMoney(filterBounds.priceMin);
        if (priceMaxEl && filterBounds.priceMax) priceMaxEl.placeholder = formatMapMoney(filterBounds.priceMax);
        if (areaMinEl && filterBounds.areaMin) areaMinEl.placeholder = `${filterBounds.areaMin.toLocaleString('fa-IR')} متر`;
        if (areaMaxEl && filterBounds.areaMax) areaMaxEl.placeholder = `${filterBounds.areaMax.toLocaleString('fa-IR')} متر`;

        const serverFilters = settings?.filters || {};
        if (serverFilters.neighborhood) filterState.neighborhood = serverFilters.neighborhood;
        if (serverFilters.rooms) filterState.rooms = serverFilters.rooms;
        if (serverFilters.freshness) filterState.freshness = serverFilters.freshness;
        if (serverFilters.value) filterState.valueTier = serverFilters.value;
        if (serverFilters.price_min) filterState.priceMin = String(serverFilters.price_min);
        if (serverFilters.price_max) filterState.priceMax = String(serverFilters.price_max);
        if (serverFilters.deposit_min) filterState.depositMin = String(serverFilters.deposit_min);
        if (serverFilters.deposit_max) filterState.depositMax = String(serverFilters.deposit_max);
        if (serverFilters.rent_min) filterState.rentMin = String(serverFilters.rent_min);
        if (serverFilters.rent_max) filterState.rentMax = String(serverFilters.rent_max);
        if (serverFilters.area_min) filterState.areaMin = String(serverFilters.area_min);
        if (serverFilters.area_max) filterState.areaMax = String(serverFilters.area_max);
        if (serverFilters.year_min) filterState.yearMin = String(serverFilters.year_min);
        if (serverFilters.year_max) filterState.yearMax = String(serverFilters.year_max);
        if (serverFilters.elevator === '1') filterState.elevator = true;
        if (serverFilters.parking === '1') filterState.parking = true;
        if (serverFilters.storage === '1') filterState.storage = true;

        toggle?.addEventListener('click', () => {
            const open = panel?.hasAttribute('hidden');
            if (open) {
                panel.removeAttribute('hidden');
                toggle.setAttribute('aria-expanded', 'true');
            } else {
                panel.setAttribute('hidden', '');
                toggle.setAttribute('aria-expanded', 'false');
            }
        });
        resetBtn?.addEventListener('click', resetAdvancedFilters);
        const debouncedApply = () => {
            clearTimeout(applyAdvancedFilters._timer);
            applyAdvancedFilters._timer = setTimeout(applyAdvancedFilters, 280);
        };
        [
            'mkMapPriceMin', 'mkMapPriceMax', 'mkMapDepositMin', 'mkMapDepositMax',
            'mkMapRentMin', 'mkMapRentMax', 'mkMapAreaMin', 'mkMapAreaMax',
            'mkMapYearMin', 'mkMapYearMax',
        ].forEach((id) => {
            const el = document.getElementById(id);
            bindFormattedNumericInput(el, { onChange: debouncedApply });
            el?.addEventListener('change', applyAdvancedFilters);
        });
        [
            'mkMapRooms', 'mkMapFreshness', 'mkMapValueTier', 'mkMapTxMode',
            'mkMapNeighborhood', 'mkMapElevator', 'mkMapParking', 'mkMapStorage',
            'mkMapShowRings',
        ].forEach((id) => {
            const el = document.getElementById(id);
            el?.addEventListener('change', applyAdvancedFilters);
            el?.addEventListener('input', debouncedApply);
        });
        syncFilterInputs();
    }

    function setupSplitList() {
        const panel = document.getElementById('mkMapPanel');
        const list = document.getElementById('mkMapList');
        const toggle = document.getElementById('mkMapListToggle');
        const closeBtn = document.getElementById('mkMapListClose');

        function setListOpen(open) {
            if (!list || !panel) return;
            list.hidden = !open;
            panel.classList.toggle('mk-map-panel--split', open);
            toggle?.classList.toggle('is-active', open);
            if (open) {
                refreshListPanel();
                setTimeout(() => map.invalidateSize(), 120);
            } else {
                setTimeout(() => map.invalidateSize(), 120);
            }
        }

        toggle?.addEventListener('click', () => setListOpen(list?.hidden));
        closeBtn?.addEventListener('click', () => setListOpen(false));
        map.on('moveend', () => {
            if (list && !list.hidden) refreshListPanel();
        });
        setListOpen(false);
    }

    function redrawActiveHeatLayer() {
        const heatLayer = layers[activeMode];
        if (!heatLayer?._isHeatLayer) return;
        const source = heatLayer._heatSource || layers._visible || getFilteredMarkers();
        const opts = computeHeatLayerOptions(
            source,
            heatLayer._heatPalette,
            map,
            { weighted: heatLayer._heatWeighted },
        );
        heatLayer.setOptions?.({ radius: opts.radius });
        heatLayer.redraw?.();
    }

    function refreshLayers() {
        const keepId = selectedMarkerId;
        if (layers[activeMode]) map.removeLayer(layers[activeMode]);
        layers = buildLayers();
        if (!layers[activeMode]) activeMode = 'markers';
        if (layers[activeMode]) {
            map.addLayer(layers[activeMode]);
        }
        syncMarkerRegistry();
        if (keepId != null && markerRegistry[keepId]) selectMarker(keepId);
        updateMapChrome(activeMode);
        refreshListPanel();
        if (activeMode.startsWith('heat_')) {
            requestAnimationFrame(() => redrawActiveHeatLayer());
        }
    }

    if (fullBounds.isValid()) {
        if (allMarkers.length === 1) {
            map.setView([allMarkers[0].lat, allMarkers[0].lng], focusMaxZoom);
        } else {
            map.fitBounds(fullBounds, {
                padding: [56, 56],
                maxZoom: focusMaxZoom,
                animate: false,
            });
        }
    } else if (allMarkers.length) {
        map.setView([allMarkers[0].lat, allMarkers[0].lng], 12);
    }

    layers = buildLayers();
    syncMarkerRegistry();
    if (!layers[activeMode]) activeMode = 'markers';
    map.addLayer(layers[activeMode] || layers.markers);

    mapPro?.updateZoomBadge?.();
    setTimeout(() => {
        map.invalidateSize();
        mapPro?.updateZoomBadge?.();
        if (layers[activeMode]?._isHeatLayer) {
            redrawActiveHeatLayer();
        }
    }, 150);

    const hint = document.querySelector('.mk-map-overlay--hint');
    const legend = document.getElementById('mkMapLegend');
    const legendBody = document.getElementById('mkMapLegendBody');
    const legendBadge = document.getElementById('mkMapLegendBadge');
    const legendCount = document.getElementById('mkMapLegendCount');
    const modesBar = document.getElementById('mkMapModesBar');
    const modeButtons = document.querySelectorAll('#mkMapModes .mk-map-mode');
    const filterButtons = document.querySelectorAll('#mkMapFilters .mk-map-filter');

    const legendMeta = {
        markers: { badge: 'نقاط' },
        market: { badge: 'بازار' },
        value: { badge: 'رنگ قیمت' },
        full_deposit: { badge: 'رهن کامل' },
        grid: { badge: 'شبکه' },
        heat_density: { badge: 'هیت تراکم' },
        heat_price: { badge: 'هیت قیمت' },
        heat_pps: { badge: 'هیت متر' },
    };

    function marketLegendHtml() {
        const st = layerStats.market || {};
        return `<div class="mk-map-legend-items" role="list">
            <span class="mk-map-legend-item" role="listitem"><i class="mk-map-legend-dot mk-map-legend-dot--under" aria-hidden="true"></i>زیر بازار<em>${(st.under || 0).toLocaleString('fa-IR')}</em></span>
            <span class="mk-map-legend-item" role="listitem"><i class="mk-map-legend-dot mk-map-legend-dot--fair" aria-hidden="true"></i>متعارف<em>${(st.fair || 0).toLocaleString('fa-IR')}</em></span>
            <span class="mk-map-legend-item" role="listitem"><i class="mk-map-legend-dot mk-map-legend-dot--over" aria-hidden="true"></i>بالای بازار<em>${(st.over || 0).toLocaleString('fa-IR')}</em></span>
        </div>`;
    }

    function markersLegendHtml() {
        const ringHint = showRings
            ? '<span class="mk-map-legend-hint">دایره = محدوده تقریبی</span>'
            : '';
        if (sellerFilter === 'consultant') {
            return `<div class="mk-map-legend-items">${ringHint}<span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--consultant" aria-hidden="true"></i>مشاور</span><span class="mk-map-legend-hint">کلیک برای جزئیات</span></div>`;
        }
        if (sellerFilter === 'disguised') {
            return `<div class="mk-map-legend-items">${ringHint}<span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--disguised" aria-hidden="true"></i>مشاور پنهان</span><span class="mk-map-legend-hint">کلیک برای جزئیات</span></div>`;
        }
        if (sellerFilter === 'genuine' || sellerFilter === 'personal') {
            return `<div class="mk-map-legend-items">${ringHint}<span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--genuine" aria-hidden="true"></i>مالک واقعی</span><span class="mk-map-legend-hint">کلیک برای جزئیات</span></div>`;
        }
        return `<div class="mk-map-legend-items">
            ${ringHint}
            <span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--consultant" aria-hidden="true"></i>مشاور</span>
            <span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--disguised" aria-hidden="true"></i>مشاور پنهان</span>
            <span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--genuine" aria-hidden="true"></i>مالک واقعی</span>
            <span class="mk-map-legend-hint">کلیک برای جزئیات</span>
        </div>`;
    }

    const filterValueLabel = settings?.filter_value_label || settings?.filterValueLabel || 'قیمت';
    const legendTemplates = {
        value: () => `${buildMapLegendScale('value', layerStats.value)}<span class="mk-map-legend-hint">کلیک روی هر نقطه برای جزئیات</span>`,
        full_deposit: () => `${buildMapLegendScale('full_deposit', layerStats.full_deposit)}<span class="mk-map-legend-hint">کلیک روی هر نقطه برای جزئیات</span>`,
        grid: () => buildMapLegendScale('grid', layerStats.grid),
        market: () => marketLegendHtml(),
        heat_density: () => `${buildMapLegendScale('heat_density', layerStats.heat_density)}<span class="mk-map-legend-hint">هاله نرم — تراکم آگهی</span>`,
        heat_price: () => `${buildMapLegendScale('heat_price', layerStats.heat_price)}<span class="mk-map-legend-hint">وزن بر اساس ${filterValueLabel}</span>`,
        heat_pps: () => `${buildMapLegendScale('heat_pps', layerStats.heat_pps)}<span class="mk-map-legend-hint">قیمت هر متر مربع</span>`,
    };

    function updateMapChrome(mode) {
        if (hint) {
            hint.hidden = !['markers', 'market', 'value', 'full_deposit'].includes(mode)
                || map.getZoom() >= clusterDisableZoom;
        }
        const meta = legendMeta[mode] || legendMeta.markers;
        const count = layers._count ?? getFilteredMarkers().length;
        if (legendBadge) legendBadge.textContent = meta.badge;
        if (legendCount) legendCount.textContent = count.toLocaleString('fa-IR');
        if (legendBody) {
            if (mode === 'markers') legendBody.innerHTML = markersLegendHtml();
            else if (mode === 'market') legendBody.innerHTML = marketLegendHtml();
            else legendBody.innerHTML = legendTemplates[mode]?.() || markersLegendHtml();
        }
        if (legend) {
            legend.dataset.mode = mode;
            legend.classList.toggle('mk-map-legend--heat', mode.startsWith('heat_'));
        }
        const stageEl = document.querySelector('.mk-map-stage');
        if (stageEl) stageEl.dataset.heatMode = mode.startsWith('heat_') ? 'true' : 'false';
        modeButtons.forEach(btn => {
            const on = btn.dataset.mode === mode;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
    }

    function setMapMode(mode) {
        if (mode === activeMode) return;
        if (layers[activeMode]) map.removeLayer(layers[activeMode]);
        activeMode = mode;
        layers = buildLayers();
        if (!layers[activeMode]) activeMode = 'markers';
        map.addLayer(layers[activeMode] || layers.markers);
        syncMarkerRegistry();
        if (selectedMarkerId != null && markerRegistry[selectedMarkerId]) {
            selectMarker(selectedMarkerId);
        }
        updateMapChrome(activeMode);
        refreshListPanel();
        if (activeMode.startsWith('heat_')) {
            setTimeout(() => {
                map.invalidateSize();
                redrawActiveHeatLayer();
            }, 80);
        }
    }

    function setSellerFilter(filter) {
        if (filter === sellerFilter) return;
        sellerFilter = filter;
        filterButtons.forEach(btn => {
            const on = btn.dataset.filter === filter;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        refreshLayers();
    }

    if (!mapModesEnabled && modesBar) modesBar.hidden = true;

    modeButtons.forEach(btn => {
        btn.addEventListener('click', () => setMapMode(btn.dataset.mode));
    });

    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => setSellerFilter(btn.dataset.filter));
    });

    let zoomRefreshTimer;
    map.on('zoomend', () => {
        if (hint) {
            if (activeMode.startsWith('heat_') || activeMode === 'grid') {
                hint.hidden = true;
            } else if (['markers', 'market', 'value', 'full_deposit'].includes(activeMode)) {
                hint.hidden = map.getZoom() >= clusterDisableZoom;
            }
        }
        if (activeMode === 'grid' || activeMode.startsWith('heat_')) {
            clearTimeout(zoomRefreshTimer);
            zoomRefreshTimer = setTimeout(() => {
                if (activeMode.startsWith('heat_')) {
                    redrawActiveHeatLayer();
                } else {
                    refreshLayers();
                }
            }, 80);
        }
    });

    map.on('moveend', () => {
        if (activeMode.startsWith('heat_')) {
            clearTimeout(zoomRefreshTimer);
            zoomRefreshTimer = setTimeout(() => redrawActiveHeatLayer(), 80);
        }
    });

    map.whenReady(() => {
        if (activeMode.startsWith('heat_')) {
            setTimeout(() => redrawActiveHeatLayer(), 200);
        }
    });

    setupAdvancedFilters();
    setupSplitList();
    updateMapChrome(activeMode);
}
