(function () {
    'use strict';

    function greetingMeta(h) {
        if (h >= 5 && h < 12) {
            return { text: 'صبح بخیر', icon: 'fa-sun', tone: 'morning' };
        }
        if (h >= 12 && h < 17) {
            return { text: 'ظهر بخیر', icon: 'fa-sun', tone: 'noon' };
        }
        if (h >= 17 && h < 21) {
            return { text: 'عصر بخیر', icon: 'fa-cloud-sun', tone: 'evening' };
        }
        return { text: 'شب بخیر', icon: 'fa-moon', tone: 'night' };
    }

    function initGreeting() {
        const meta = greetingMeta(new Date().getHours());
        const textEl = document.getElementById('wsHomeGreeting');
        const textMob = document.getElementById('wsHomeGreetingMob');
        const iconEl = document.getElementById('wsHomeGreetingIcon');
        if (textEl) textEl.textContent = meta.text;
        if (textMob) textMob.textContent = meta.text;
        if (iconEl) {
            iconEl.className = `wsh2-header__greet-icon fas ${meta.icon} is-${meta.tone}`;
        }
        const mobAvatarIcon = document.querySelector('.wsh2-mob-header .wsh2-header__avatar i');
        if (mobAvatarIcon) {
            mobAvatarIcon.className = `fas ${meta.icon} is-${meta.tone}`;
        }
    }

    function initQuickAnchors() {
        document.querySelectorAll('[data-wsh2-anchor="1"]').forEach((link) => {
            link.addEventListener('click', (e) => {
                const href = link.getAttribute('href') || '';
                if (!href.startsWith('#')) return;
                const target = document.querySelector(href);
                if (!target) return;
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                const input = target.querySelector('textarea, input');
                if (input) {
                    try { input.focus({ preventScroll: true }); } catch (err) { input.focus(); }
                }
            });
        });
    }

    function initHomeCharts() {
        if (typeof window.initCharts === 'function' && window.wsCharts && window.Chart) {
            initCharts(window.wsCharts);
        }
    }

    function resizeHomeCharts() {
        if (!window.Chart || typeof Chart.getChart !== 'function') return;
        ['chart-activity', 'chart-status'].forEach((id) => {
            const canvas = document.getElementById(id);
            if (!canvas) return;
            const inst = Chart.getChart(canvas);
            if (inst) {
                try { inst.resize(); } catch (e) { /* ignore */ }
            }
        });
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function isSafeHttpUrl(url) {
        if (!url || typeof url !== 'string') return false;
        try {
            const parsed = new URL(url, window.location.origin);
            return parsed.protocol === 'http:' || parsed.protocol === 'https:';
        } catch (e) {
            return false;
        }
    }

    function initGlobalSearch() {
        const input = document.getElementById('crmSearchInput');
        const results = document.getElementById('crmSearchResults');
        const clearBtn = document.getElementById('crmSearchClear');
        const loadingEl = document.getElementById('crmSearchLoading');
        if (!input || !results) return;

        let timer = null;
        let seq = 0;
        let abortCtrl = null;
        const searchUrl = input.dataset.url || '/workspace/crm/search/';

        function setLoading(on) {
            if (loadingEl) loadingEl.hidden = !on;
            syncTrailing();
        }

        function syncTrailing() {
            const hasText = input.value.trim().length > 0;
            const loading = loadingEl && !loadingEl.hidden;
            if (clearBtn) clearBtn.hidden = !hasText || loading;
        }

        function closeResults() {
            results.hidden = true;
            input.setAttribute('aria-expanded', 'false');
        }

        function openResults() {
            results.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }

        function renderResults(data) {
            const parts = [];
            if (data.contacts?.length) {
                parts.push('<div class="crm-search-group"><div class="crm-search-group-title">مخاطبین</div>');
                data.contacts.forEach((c) => {
                    if (!isSafeHttpUrl(c.url)) return;
                    const name = escapeHtml(c.name);
                    const meta = escapeHtml(`${c.type || ''}${c.phone ? ` · ${c.phone}` : ''}`);
                    parts.push(`<a href="${escapeHtml(c.url)}" class="crm-search-item" role="option"><span>${name}</span><span class="crm-search-item-meta">${meta}</span></a>`);
                });
                parts.push('</div>');
            }
            if (data.properties?.length) {
                parts.push('<div class="crm-search-group"><div class="crm-search-group-title">املاک</div>');
                data.properties.forEach((p) => {
                    if (!isSafeHttpUrl(p.url)) return;
                    const title = escapeHtml(p.title);
                    const meta = escapeHtml(`${p.deal_mode || ''}${p.city ? ` · ${p.city}` : ''}`);
                    parts.push(`<a href="${escapeHtml(p.url)}" class="crm-search-item" role="option"><span>${title}</span><span class="crm-search-item-meta">${meta}</span></a>`);
                });
                parts.push('</div>');
            }
            if (!parts.length) {
                results.innerHTML = '<div class="crm-empty-text wsh-search__empty" role="status">نتیجه‌ای یافت نشد</div>';
            } else {
                results.innerHTML = parts.join('');
            }
            openResults();
        }

        async function runSearch(q) {
            const mySeq = ++seq;
            if (abortCtrl) abortCtrl.abort();
            abortCtrl = new AbortController();
            setLoading(true);
            try {
                const res = await fetch(`${searchUrl}?q=${encodeURIComponent(q)}`, {
                    signal: abortCtrl.signal,
                    headers: { Accept: 'application/json' },
                });
                if (!res.ok) throw new Error('bad status');
                const data = await res.json();
                if (mySeq !== seq) return;
                renderResults(data);
            } catch (e) {
                if (e.name === 'AbortError') return;
                if (mySeq !== seq) return;
                results.innerHTML = '<div class="crm-empty-text wsh-search__empty wsh-search__empty--err" role="alert">خطا در جستجو — دوباره تلاش کنید</div>';
                openResults();
            } finally {
                if (mySeq === seq) setLoading(false);
            }
        }

        input.addEventListener('input', () => {
            clearTimeout(timer);
            syncTrailing();
            const q = input.value.trim();
            if (q.length < 2) {
                seq += 1;
                if (abortCtrl) abortCtrl.abort();
                setLoading(false);
                closeResults();
                results.innerHTML = '';
                return;
            }
            timer = setTimeout(() => runSearch(q), 250);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                input.value = '';
                syncTrailing();
                closeResults();
                results.innerHTML = '';
            }
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                input.value = '';
                syncTrailing();
                closeResults();
                results.innerHTML = '';
                input.focus();
            });
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#crmGlobalSearch')) closeResults();
        });

        syncTrailing();
    }

    function isoDate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

    function initReminderTabs() {
        const root = document.getElementById('wshReminders');
        const list = document.getElementById('wshRemindersList');
        if (!root || !list) return;

        const tabs = root.querySelectorAll('[data-wsh-reminder-tab]');
        const items = list.querySelectorAll('.wsh-reminders__row[data-wsh-reminder-date], .wsh-reminders__row[data-wsh-reminder-scope]');
        const emptyAll = document.getElementById('wshRemindersEmpty');
        const emptyTab = document.getElementById('wshRemindersTabEmpty');
        const hint = document.getElementById('wshRemindersHint');
        if (!tabs.length) return;

        const today = isoDate(new Date());
        const tomorrow = isoDate(new Date(Date.now() + 86400000));
        const weekEnd = isoDate(new Date(Date.now() + 7 * 86400000));

        function matchesTab(item, tab) {
            const scope = item.getAttribute('data-wsh-reminder-scope') || '';
            const date = item.getAttribute('data-wsh-reminder-date') || '';
            if (tab === 'all') return true;
            if (tab === 'today') {
                return scope.includes('today') || date === today;
            }
            if (tab === 'tomorrow') {
                return date === tomorrow;
            }
            if (tab === 'week') {
                if (scope.includes('today')) return true;
                if (!date) return false;
                return date >= today && date <= weekEnd;
            }
            return true;
        }

        function applyTab(tab) {
            let visible = 0;
            items.forEach((item) => {
                const show = matchesTab(item, tab);
                item.hidden = !show;
                if (show) visible += 1;
            });
            if (emptyAll) emptyAll.hidden = items.length > 0;
            if (emptyTab) emptyTab.hidden = visible > 0 || items.length === 0;
            tabs.forEach((btn) => {
                const active = btn.dataset.wshReminderTab === tab;
                btn.classList.toggle('is-active', active);
                btn.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            if (hint) hint.hidden = tab !== 'all';
        }

        tabs.forEach((btn) => {
            btn.addEventListener('click', () => applyTab(btn.dataset.wshReminderTab || 'all'));
        });

        applyTab('all');
    }

    function looksLikeIranMobile(value) {
        const digits = String(value || '').replace(/\D/g, '');
        return /^09\d{9}$/.test(digits) || /^9\d{9}$/.test(digits) || /^989\d{9}$/.test(digits);
    }

    function guardHomeFilesSearchInput(input) {
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('autocorrect', 'off');
        input.setAttribute('spellcheck', 'false');
        input.setAttribute('data-lpignore', 'true');
        input.setAttribute('data-1p-ignore', 'true');
        input.setAttribute('data-form-type', 'other');
        if (!input.name) input.name = 'mk_home_files_filter';
        input.setAttribute('readonly', 'readonly');
        input.addEventListener('focus', () => input.removeAttribute('readonly'), { once: true });
    }

    function clearPhoneAutofill(input) {
        const value = input.value.trim();
        if (!value || !looksLikeIranMobile(value)) return false;
        input.value = '';
        return true;
    }

    function dedupeHomeFilesLocOptions() {
        const sel = document.getElementById('homeFilesFilterLoc');
        if (!sel) return;
        const seen = new Set();
        [...sel.options].forEach((opt, idx) => {
            if (idx === 0) return;
            const key = (opt.value || '').toLowerCase();
            if (!key || seen.has(key)) {
                opt.remove();
            } else {
                seen.add(key);
            }
        });
    }

    function initFilesTxTabs() {
        const root = document.querySelector('.wsh-files');
        const filterTx = document.getElementById('homeFilesFilterTx');
        if (!root || !filterTx) return;
        const tabs = root.querySelectorAll('[data-wsh-files-tx]');
        if (!tabs.length) return;

        const syncActive = () => {
            const val = filterTx.value;
            tabs.forEach((btn) => {
                const v = btn.getAttribute('data-wsh-files-tx') ?? '';
                const active = v === val;
                btn.classList.toggle('is-active', active);
                btn.setAttribute('aria-selected', active ? 'true' : 'false');
            });
        };

        tabs.forEach((btn) => {
            btn.addEventListener('click', () => {
                filterTx.value = btn.getAttribute('data-wsh-files-tx') ?? '';
                filterTx.dispatchEvent(new Event('change', { bubbles: true }));
                syncActive();
            });
        });
        filterTx.addEventListener('change', syncActive);
        syncActive();
    }

    function initFilesAdvFilters() {
        const det = document.querySelector('.wsh-files__adv-filters');
        if (!det) return;
        const mq = window.matchMedia('(min-width: 768px)');
        const sync = () => {
            if (mq.matches) det.setAttribute('open', '');
        };
        sync();
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', sync);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(sync);
        }
    }

    function initFileSearch() {
        const search = document.getElementById('homeFilesSearch');
        const table = document.getElementById('homeFilesTable');
        const cardsRoot = document.getElementById('homeFilesCards');
        const empty = document.getElementById('homeFilesEmpty');
        const filterTx = document.getElementById('homeFilesFilterTx');
        const filterLoc = document.getElementById('homeFilesFilterLoc');
        const filterFmt = document.getElementById('homeFilesFilterFmt');
        if (!search || !table) return;

        dedupeHomeFilesLocOptions();
        guardHomeFilesSearchInput(search);
        const rows = table.querySelectorAll('tbody tr');
        const cards = cardsRoot ? cardsRoot.querySelectorAll('.wsh-files__card') : [];
        const wrap = table.closest('.mk-table-wrap');

        const applyFilter = () => {
            const q = search.value.trim().toLowerCase();
            const tx = filterTx ? filterTx.value : '';
            const loc = filterLoc ? filterLoc.value.trim().toLowerCase() : '';
            const fmt = filterFmt ? filterFmt.value.trim().toLowerCase() : '';
            let visible = 0;
            const matchItem = (el) => {
                const matchSearch = !q || (el.dataset.search || '').toLowerCase().includes(q);
                const matchTx = !tx || (el.dataset.tx || '') === tx;
                const matchLoc = !loc || (el.dataset.loc || '').includes(loc);
                const matchFmt = !fmt || (el.dataset.fmt || '') === fmt;
                return matchSearch && matchTx && matchLoc && matchFmt;
            };
            rows.forEach((row) => {
                const match = matchItem(row);
                row.hidden = !match;
                if (match) visible += 1;
            });
            cards.forEach((card) => {
                const match = matchItem(card);
                card.hidden = !match;
            });
            const noResults = visible === 0 && rows.length > 0;
            if (empty) empty.hidden = !noResults;
            if (wrap) wrap.hidden = noResults;
            if (cardsRoot) cardsRoot.hidden = noResults;
        };

        const sweepAutofill = () => {
            if (clearPhoneAutofill(search)) applyFilter();
        };

        search.addEventListener('input', applyFilter);
        [filterTx, filterLoc, filterFmt].forEach((el) => {
            if (el) el.addEventListener('change', applyFilter);
        });
        sweepAutofill();
        requestAnimationFrame(() => requestAnimationFrame(sweepAutofill));
        window.setTimeout(sweepAutofill, 120);
        window.setTimeout(sweepAutofill, 500);
        applyFilter();
    }

    function initInsightsDisclosure() {
        const targets = [
            ...document.querySelectorAll('.wsh-insights, [data-wsh2-analytics]'),
        ];
        if (!targets.length) return;
        const mq = window.matchMedia('(min-width: 768px)');
        const sync = () => {
            targets.forEach((el) => {
                if (mq.matches) el.setAttribute('open', '');
                else el.removeAttribute('open');
            });
            resizeHomeCharts();
        };
        sync();
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', sync);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(sync);
        }
        targets.forEach((el) => {
            el.addEventListener('toggle', () => {
                if (el.open) resizeHomeCharts();
            });
        });
    }

    function initReveal() {
        const root = document.querySelector('.ws-home-v2') || document.querySelector('.wsh-dashboard');
        if (!root) return;
        requestAnimationFrame(() => root.classList.add('is-ready'));
    }

    function initResizeWatch() {
        let t = null;
        const onResize = () => {
            clearTimeout(t);
            t = setTimeout(resizeHomeCharts, 120);
        };
        window.addEventListener('resize', onResize);
        window.addEventListener('orientationchange', onResize);
    }

    document.addEventListener('DOMContentLoaded', () => {
        initGreeting();
        initQuickAnchors();
        initGlobalSearch();
        initReminderTabs();
        initFilesTxTabs();
        initFilesAdvFilters();
        initFileSearch();
        initHomeCharts();
        initResizeWatch();
        initInsightsDisclosure();
        initReveal();
    });
})();
