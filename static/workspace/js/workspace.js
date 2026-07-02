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

function initCrmMobileMenuDock() {
    const row = document.querySelector('.crm-top-nav-row');
    const toggle = document.getElementById('sidebarToggle');
    const main = document.querySelector('.ws-main');
    if (!row || !toggle || !main) return;

    const mq = window.matchMedia('(max-width: 768px)');

    function dock() {
        if (mq.matches) {
            if (toggle.parentElement !== row) row.insertBefore(toggle, row.firstChild);
            toggle.classList.add('ws-mobile-menu--crm-inline');
        } else {
            toggle.classList.remove('ws-mobile-menu--crm-inline');
            if (toggle.parentElement !== main) main.insertBefore(toggle, main.firstChild);
        }
    }

    dock();
    mq.addEventListener('change', dock);
}

document.addEventListener('DOMContentLoaded', () => {
    // Sidebar mobile
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('wsSidebar');

    function setSidebarOpen(open) {
        if (!sidebar) return;
        sidebar.classList.toggle('open', open);
        document.body.classList.toggle('ws-sidebar-open', open);
    }

    if (toggle && sidebar) {
        toggle.addEventListener('click', () => setSidebarOpen(!sidebar.classList.contains('open')));
        document.addEventListener('click', e => {
            if (!sidebar.classList.contains('open')) return;
            if (sidebar.contains(e.target) || toggle.contains(e.target)) return;
            setSidebarOpen(false);
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && sidebar.classList.contains('open')) {
                setSidebarOpen(false);
            }
        });
    }

    initCrmMobileMenuDock();

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

    // Auto-open from server
    const openId = document.body.dataset.openModal;
    if (openId) WSModal.open(openId);

    // Auto-dismiss toasts
    document.querySelectorAll('[data-auto-dismiss]').forEach(el => {
        setTimeout(() => el.remove(), 5000);
    });

    // Upload zone
    initUploadZone();
    initSettingsModal();

    // Tabs
    document.querySelectorAll('[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            const parent = btn.closest('.ws-card, .ws-modal-body, .ws-content');
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
});

function initDatasetBulkSelect() {
    const selectAll = document.getElementById('dsSelectAll');
    const checks = document.querySelectorAll('.mk-ds-check');
    const bulkBar = document.getElementById('dsBulkBar');
    const bulkCount = document.getElementById('dsBulkCount');
    const bulkClear = document.getElementById('dsBulkClear');
    const bulkDelete = document.getElementById('dsBulkDelete');
    const bulkForm = document.getElementById('dsBulkDeleteForm');
    const bulkIds = document.getElementById('dsBulkDeleteIds');
    if (!checks.length) return;

    function selected() {
        return [...checks].filter(c => c.checked);
    }

    function syncRowHighlight() {
        checks.forEach(c => {
            const row = c.closest('tr[data-id], .mk-ds-card[data-id]');
            if (row) row.classList.toggle('is-selected', c.checked);
        });
    }

    function updateBulk() {
        const picked = selected();
        const n = picked.length;
        if (bulkBar) {
            bulkBar.hidden = n === 0;
            bulkBar.classList.toggle('is-visible', n > 0);
        }
        if (bulkCount) bulkCount.textContent = n;
        if (selectAll) {
            selectAll.checked = n > 0 && n === checks.length;
            selectAll.indeterminate = n > 0 && n < checks.length;
        }
        syncRowHighlight();
    }

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            checks.forEach(c => { c.checked = selectAll.checked; });
            updateBulk();
        });
    }
    checks.forEach(c => c.addEventListener('change', updateBulk));

    if (bulkClear) {
        bulkClear.addEventListener('click', () => {
            checks.forEach(c => { c.checked = false; });
            if (selectAll) selectAll.checked = false;
            updateBulk();
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
    const loc = parseLocationDirs(dirs);
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
                                font: { family: 'Vazirmatn', size: useTrendStyle ? 10 : 11 },
                                maxRotation: 0,
                                maxTicksLimit: useTrendStyle ? 7 : undefined,
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

function buildMapMarkerPopup(m) {
    const priceLine = m.price_label || (m.price ? Number(m.price).toLocaleString('fa-IR') : '—');
    const sellerClass = m.is_consultant ? 'consultant' : 'personal';
    const sellerLabel = m.seller_type || (m.is_consultant ? 'مشاور' : 'شخصی');
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
    if (filterState.priceMin != null && filterState.priceMin !== '') n += 1;
    if (filterState.priceMax != null && filterState.priceMax !== '') n += 1;
    if (filterState.areaMin != null && filterState.areaMin !== '') n += 1;
    if (filterState.areaMax != null && filterState.areaMax !== '') n += 1;
    if (filterState.rooms && filterState.rooms !== 'all') n += 1;
    if (filterState.freshness && filterState.freshness !== 'all') n += 1;
    if (filterState.underOnly) n += 1;
    return n;
}

function normalizeMoneyInput(val) {
    const n = Number(parseFormattedNumber(val) || val);
    if (!n || n <= 0) return null;
    if (n < 100000) return Math.round(n * 1_000_000);
    return n;
}

function applyMapMarkerFilters(markers, filterState, sellerFilter) {
    let list = markers;
    if (sellerFilter === 'consultant') list = list.filter(m => m.is_consultant);
    else if (sellerFilter === 'personal') list = list.filter(m => !m.is_consultant);

    const pMin = filterState.priceMin != null && filterState.priceMin !== '' ? normalizeMoneyInput(filterState.priceMin) : null;
    const pMax = filterState.priceMax != null && filterState.priceMax !== '' ? normalizeMoneyInput(filterState.priceMax) : null;
    const aMin = filterState.areaMin != null && filterState.areaMin !== '' ? Number(parseFormattedNumber(filterState.areaMin) || filterState.areaMin) : null;
    const aMax = filterState.areaMax != null && filterState.areaMax !== '' ? Number(parseFormattedNumber(filterState.areaMax) || filterState.areaMax) : null;

    return list.filter((m) => {
        const fv = Number(m.filter_value) || 0;
        const area = Number(m.area) || 0;
        if (pMin != null && fv > 0 && fv < pMin) return false;
        if (pMax != null && fv > 0 && fv > pMax) return false;
        if (aMin != null && area > 0 && area < aMin) return false;
        if (aMax != null && area > 0 && area > aMax) return false;
        if (!matchRoomsFilter(m.rooms, filterState.rooms)) return false;
        if (!matchFreshnessFilter(m.published_ts, filterState.freshness)) return false;
        if (filterState.underOnly && m.market_tier !== 'under') return false;
        return true;
    });
}

function addAccuracyRings(group, marker, showRings) {
    if (!showRings || !marker.location_radius_m) return;
    const stroke = marker.is_consultant ? '#2563eb' : '#e11d48';
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
    }[mode] || 'price';

    const labels = {
        value: { low: 'ارزان', high: 'گران' },
        full_deposit: { low: 'رهن کم', high: 'رهن زیاد' },
        grid: { low: '۱', high: `${stats?.maxCount ?? '…'}` },
    }[mode] || { low: 'ارزان', high: 'گران' };

    const caption = stats?.rangeText
        ? `<span class="mk-map-legend-caption">${stats.rangeText}</span>`
        : '';

    return `<div class="mk-map-legend-scale mk-map-legend-scale--inline">
        <div class="mk-map-legend-scale-row">
            <span class="mk-map-legend-scale-end">${labels.low}</span>
            <div class="mk-map-legend-scale-track" aria-hidden="true">
                <span class="mk-map-legend-scale-bar mk-map-legend-scale-bar--${barClass}"></span>
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
    let activeMode = 'markers';
    let showRings = false;
    let layers = {};
    let layerStats = {};
    let markerRegistry = {};
    let highlightedMarkerId = null;
    let selectedMarkerId = null;
    const filterState = {
        priceMin: '',
        priceMax: '',
        areaMin: '',
        areaMax: '',
        rooms: 'all',
        freshness: 'all',
        underOnly: false,
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
            if (m.is_consultant) pinClass += ' mk-map-pin--consultant-ring';
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
            pinClass += ` mk-map-pin--${m.is_consultant ? 'consultant' : 'personal'}`;
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
        if (t < 0.2) return '#c7d2fe';
        if (t < 0.45) return '#818cf8';
        if (t < 0.7) return '#a855f7';
        if (t < 0.85) return '#f97316';
        return '#dc2626';
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
                fillOpacity: 0.32 + intensity * 0.48,
                color: gridFillColor(intensity),
                weight: 1.5,
                opacity: 0.5 + intensity * 0.35,
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

        layerStats = {
            value: value.stats,
            full_deposit: fullDeposit.stats,
            grid: grid.stats,
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
        const areaMinEl = document.getElementById('mkMapAreaMin');
        const areaMaxEl = document.getElementById('mkMapAreaMax');
        const roomsEl = document.getElementById('mkMapRooms');
        const freshEl = document.getElementById('mkMapFreshness');
        const underEl = document.getElementById('mkMapUnderOnly');
        const ringsEl = document.getElementById('mkMapShowRings');
        if (priceMinEl) {
            priceMinEl.value = filterState.priceMin ? formatWithSeparators(filterState.priceMin) : '';
            priceMinEl.dataset.rawValue = filterState.priceMin ? String(filterState.priceMin) : '';
        }
        if (priceMaxEl) {
            priceMaxEl.value = filterState.priceMax ? formatWithSeparators(filterState.priceMax) : '';
            priceMaxEl.dataset.rawValue = filterState.priceMax ? String(filterState.priceMax) : '';
        }
        if (areaMinEl) {
            areaMinEl.value = filterState.areaMin ? formatWithSeparators(filterState.areaMin) : '';
            areaMinEl.dataset.rawValue = filterState.areaMin ? String(filterState.areaMin) : '';
        }
        if (areaMaxEl) {
            areaMaxEl.value = filterState.areaMax ? formatWithSeparators(filterState.areaMax) : '';
            areaMaxEl.dataset.rawValue = filterState.areaMax ? String(filterState.areaMax) : '';
        }
        if (roomsEl) roomsEl.value = filterState.rooms;
        if (freshEl) freshEl.value = filterState.freshness;
        if (underEl) underEl.checked = filterState.underOnly;
        if (ringsEl) ringsEl.checked = showRings;
        updateFilterBadge();
    }

    function applyAdvancedFilters() {
        const priceMinEl = document.getElementById('mkMapPriceMin');
        const priceMaxEl = document.getElementById('mkMapPriceMax');
        const areaMinEl = document.getElementById('mkMapAreaMin');
        const areaMaxEl = document.getElementById('mkMapAreaMax');
        const roomsEl = document.getElementById('mkMapRooms');
        const freshEl = document.getElementById('mkMapFreshness');
        const underEl = document.getElementById('mkMapUnderOnly');
        const ringsEl = document.getElementById('mkMapShowRings');
        filterState.priceMin = readFormattedInput(priceMinEl);
        filterState.priceMax = readFormattedInput(priceMaxEl);
        filterState.areaMin = readFormattedInput(areaMinEl);
        filterState.areaMax = readFormattedInput(areaMaxEl);
        filterState.rooms = roomsEl?.value || 'all';
        filterState.freshness = freshEl?.value || 'all';
        filterState.underOnly = !!underEl?.checked;
        showRings = ringsEl ? ringsEl.checked : false;
        updateFilterBadge();
        refreshLayers();
    }

    function resetAdvancedFilters() {
        filterState.priceMin = '';
        filterState.priceMax = '';
        filterState.areaMin = '';
        filterState.areaMax = '';
        filterState.rooms = 'all';
        filterState.freshness = 'all';
        filterState.underOnly = false;
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
        if (priceMinLabel) priceMinLabel.textContent = `حداقل ${label}`;
        if (priceMaxLabel) priceMaxLabel.textContent = `حداکثر ${label}`;

        const priceMinEl = document.getElementById('mkMapPriceMin');
        const priceMaxEl = document.getElementById('mkMapPriceMax');
        const areaMinEl = document.getElementById('mkMapAreaMin');
        const areaMaxEl = document.getElementById('mkMapAreaMax');
        if (priceMinEl && filterBounds.priceMin) priceMinEl.placeholder = formatMapMoney(filterBounds.priceMin);
        if (priceMaxEl && filterBounds.priceMax) priceMaxEl.placeholder = formatMapMoney(filterBounds.priceMax);
        if (areaMinEl && filterBounds.areaMin) areaMinEl.placeholder = `${filterBounds.areaMin.toLocaleString('fa-IR')} متر`;
        if (areaMaxEl && filterBounds.areaMax) areaMaxEl.placeholder = `${filterBounds.areaMax.toLocaleString('fa-IR')} متر`;

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
        ['mkMapPriceMin', 'mkMapPriceMax', 'mkMapAreaMin', 'mkMapAreaMax'].forEach((id) => {
            const el = document.getElementById(id);
            bindFormattedNumericInput(el, { onChange: debouncedApply });
            el?.addEventListener('change', applyAdvancedFilters);
        });
        ['mkMapRooms', 'mkMapFreshness', 'mkMapUnderOnly', 'mkMapShowRings'].forEach((id) => {
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
    }

    layers = buildLayers();
    syncMarkerRegistry();
    map.addLayer(layers.markers);

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
    }
    mapPro?.updateZoomBadge?.();
    setTimeout(() => {
        map.invalidateSize();
        mapPro?.updateZoomBadge?.();
    }, 80);

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
        if (sellerFilter === 'personal') {
            return `<div class="mk-map-legend-items">${ringHint}<span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--personal" aria-hidden="true"></i>شخصی</span><span class="mk-map-legend-hint">کلیک برای جزئیات</span></div>`;
        }
        return `<div class="mk-map-legend-items">
            ${ringHint}
            <span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--consultant" aria-hidden="true"></i>مشاور</span>
            <span class="mk-map-legend-item"><i class="mk-map-legend-dot mk-map-legend-dot--personal" aria-hidden="true"></i>شخصی</span>
            <span class="mk-map-legend-hint">کلیک برای جزئیات</span>
        </div>`;
    }

    const legendTemplates = {
        value: () => `${buildMapLegendScale('value', layerStats.value)}<span class="mk-map-legend-hint">کلیک روی هر نقطه برای جزئیات</span>`,
        full_deposit: () => `${buildMapLegendScale('full_deposit', layerStats.full_deposit)}<span class="mk-map-legend-hint">کلیک روی هر نقطه برای جزئیات</span>`,
        grid: () => buildMapLegendScale('grid', layerStats.grid),
        market: () => marketLegendHtml(),
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
        if (legend) legend.dataset.mode = mode;
        modeButtons.forEach(btn => {
            const on = btn.dataset.mode === mode;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
    }

    function setMapMode(mode) {
        if (!layers[mode] || mode === activeMode) return;
        map.removeLayer(layers[activeMode]);
        activeMode = mode;
        map.addLayer(layers[activeMode]);
        syncMarkerRegistry();
        if (selectedMarkerId != null && markerRegistry[selectedMarkerId]) {
            selectMarker(selectedMarkerId);
        }
        updateMapChrome(mode);
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
        if (['markers', 'market', 'value', 'full_deposit'].includes(activeMode) && hint) {
            hint.hidden = map.getZoom() >= clusterDisableZoom;
        } else if (activeMode === 'grid') {
            clearTimeout(zoomRefreshTimer);
            zoomRefreshTimer = setTimeout(() => refreshLayers(), 120);
        }
    });

    setupAdvancedFilters();
    setupSplitList();
    updateMapChrome('markers');
}
