(function () {
    'use strict';

    initTocNav();
    initDesktopTocDock();
    initCopyButtons();
    initCrmApiKeySecurity();

    function initTocNav() {
        var links = document.querySelectorAll('.apidoc-toc-link[data-target]');
        if (!links.length) return;

        var sections = [];
        links.forEach(function (link) {
            var id = link.getAttribute('data-target');
            var el = document.getElementById(id);
            if (el) sections.push({ id: id, el: el, link: link });
        });

        var activeId = null;

        function setActive(id, options) {
            options = options || {};
            if (!id || (id === activeId && !options.force)) return;

            activeId = id;
            var activeLink = null;
            links.forEach(function (link) {
                var isActive = link.getAttribute('data-target') === id;
                link.classList.toggle('is-active', isActive);
                if (isActive) activeLink = link;
            });

            if (options.scrollToc && activeLink) {
                scrollTocWithinSidebar(activeLink);
            }
        }

        function updateActiveFromScroll() {
            if (!sections.length) return;
            var marker = window.matchMedia('(min-width: 901px)').matches ? 140 : 100;
            var current = sections[0].id;

            sections.forEach(function (section) {
                var top = section.el.getBoundingClientRect().top;
                if (top <= marker) {
                    current = section.id;
                }
            });

            setActive(current);
        }

        var scrollTicking = false;
        window.addEventListener('scroll', function () {
            if (scrollTicking) return;
            scrollTicking = true;
            requestAnimationFrame(function () {
                updateActiveFromScroll();
                scrollTicking = false;
            });
        }, { passive: true });

        updateActiveFromScroll();

        links.forEach(function (link) {
            link.addEventListener('click', function (e) {
                var id = link.getAttribute('data-target');
                var target = document.getElementById(id);
                if (!target) return;

                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                setActive(id, { force: true, scrollToc: true });
                history.replaceState(null, '', '#' + id);
            });
        });

        var hash = window.location.hash.replace('#', '');
        if (hash) {
            var hashEl = document.getElementById(hash);
            if (hashEl) {
                requestAnimationFrame(function () {
                    hashEl.scrollIntoView({ behavior: 'auto', block: 'start' });
                    setActive(hash, { force: true, scrollToc: true });
                });
            }
        }
    }

    function scrollTocWithinSidebar(link) {
        var sidebarInner = document.querySelector('.apidoc-sidebar-inner');
        if (!sidebarInner || !window.matchMedia('(min-width: 901px)').matches) return;

        var linkTop = link.offsetTop;
        var linkBottom = linkTop + link.offsetHeight;
        var viewTop = sidebarInner.scrollTop;
        var viewBottom = viewTop + sidebarInner.clientHeight;
        var pad = 10;

        if (linkTop < viewTop + pad) {
            sidebarInner.scrollTop = Math.max(0, linkTop - pad);
        } else if (linkBottom > viewBottom - pad) {
            sidebarInner.scrollTop = linkBottom - sidebarInner.clientHeight + pad;
        }
    }

    function initDesktopTocDock() {
        var mq = window.matchMedia('(min-width: 901px)');
        var sidebar = document.querySelector('.apidoc-sidebar');
        var inner = document.querySelector('.apidoc-sidebar-inner');
        var layout = document.querySelector('.apidoc-layout');
        if (!sidebar || !inner || !layout) return;

        var TOP = 20;
        var dockMinHeight = 0;
        var ticking = false;

        function clearDockStyles() {
            inner.classList.remove('is-docked');
            inner.style.position = '';
            inner.style.top = '';
            inner.style.right = '';
            inner.style.left = '';
            inner.style.width = '';
            inner.style.maxHeight = '';
            sidebar.style.minHeight = '';
        }

        function applyDock() {
            if (!mq.matches) {
                clearDockStyles();
                return;
            }

            var sideRect = sidebar.getBoundingClientRect();
            var layoutRect = layout.getBoundingClientRect();
            var maxHeight = window.innerHeight - TOP * 2;
            var shouldDock = layoutRect.top <= TOP && layoutRect.bottom > TOP + 120;

            if (!shouldDock) {
                clearDockStyles();
                return;
            }

            inner.classList.add('is-docked');
            inner.style.position = 'fixed';
            inner.style.top = TOP + 'px';
            inner.style.width = Math.round(sideRect.width) + 'px';
            inner.style.maxHeight = maxHeight + 'px';

            if (document.documentElement.dir === 'rtl') {
                inner.style.right = Math.round(window.innerWidth - sideRect.right) + 'px';
                inner.style.left = 'auto';
            } else {
                inner.style.left = Math.round(sideRect.left) + 'px';
                inner.style.right = 'auto';
            }

            dockMinHeight = Math.min(inner.scrollHeight, maxHeight);
            sidebar.style.minHeight = dockMinHeight + 'px';
        }

        function scheduleDock() {
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(function () {
                applyDock();
                ticking = false;
            });
        }

        window.addEventListener('scroll', scheduleDock, { passive: true });
        window.addEventListener('resize', scheduleDock);
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', scheduleDock);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(scheduleDock);
        }
        scheduleDock();
    }

    function initCopyButtons() {
        document.querySelectorAll('.apidoc-copy-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (btn.disabled) return;

                var text = '';
                var targetId = btn.getAttribute('data-copy-id');
                var targetElId = btn.getAttribute('data-copy-target');
                var secretElId = btn.getAttribute('data-copy-secret');

                if (secretElId && window.__apidocCrmKey) {
                    text = window.__apidocCrmKey;
                } else if (targetId) {
                    var pre = document.getElementById(targetId);
                    text = pre ? pre.textContent.trim() : '';
                } else if (targetElId) {
                    var el = document.getElementById(targetElId);
                    text = el ? el.textContent.trim() : '';
                } else {
                    text = btn.getAttribute('data-copy-text') || '';
                }

                if (!text || text.indexOf('••') === 0) return;

                copyText(text).then(function () {
                    flashCopied(btn);
                }).catch(function () {
                    flashCopied(btn, true);
                });
            });
        });
    }

    function initCrmApiKeySecurity() {
        var root = document.querySelector('.apidoc[data-crm-key-url]');
        var toggle = document.getElementById('crmApiKeyToggle');
        var copyBtn = document.getElementById('crmApiKeyCopy');
        var valueEl = document.getElementById('user-crm-api-key');
        if (!root || !toggle || !copyBtn || !valueEl) return;

        var revealUrl = root.getAttribute('data-crm-key-url');
        var maskedText = valueEl.textContent.trim();
        var hideTimer = null;
        var fetching = false;

        function maskKey() {
            window.__apidocCrmKey = '';
            valueEl.textContent = maskedText;
            valueEl.classList.add('apidoc-key-value--masked');
            valueEl.classList.remove('is-revealed');
            toggle.setAttribute('aria-pressed', 'false');
            toggle.setAttribute('aria-label', 'نمایش کلید API');
            toggle.setAttribute('title', 'نمایش کلید');
            toggle.querySelector('i').className = 'fas fa-eye';
            copyBtn.disabled = true;
            if (hideTimer) {
                clearTimeout(hideTimer);
                hideTimer = null;
            }
        }

        function revealKey(key) {
            window.__apidocCrmKey = key;
            valueEl.textContent = key;
            valueEl.classList.remove('apidoc-key-value--masked');
            valueEl.classList.add('is-revealed');
            toggle.setAttribute('aria-pressed', 'true');
            toggle.setAttribute('aria-label', 'مخفی کردن کلید API');
            toggle.setAttribute('title', 'مخفی کردن');
            toggle.querySelector('i').className = 'fas fa-eye-slash';
            copyBtn.disabled = false;
            hideTimer = setTimeout(maskKey, 60000);
        }

        toggle.addEventListener('click', function () {
            if (toggle.getAttribute('aria-pressed') === 'true') {
                maskKey();
                return;
            }
            if (window.__apidocCrmKey) {
                revealKey(window.__apidocCrmKey);
                return;
            }
            if (fetching) return;
            fetching = true;
            toggle.disabled = true;

            fetch(revealUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                },
                credentials: 'same-origin',
            })
                .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
                .then(function (result) {
                    if (!result.ok || !result.data.ok || !result.data.key) {
                        throw new Error(result.data.error || 'خطا در دریافت کلید');
                    }
                    revealKey(result.data.key);
                })
                .catch(function () {
                    valueEl.textContent = 'خطا در بارگذاری — دوباره تلاش کنید';
                    setTimeout(function () { valueEl.textContent = maskedText; }, 2500);
                })
                .finally(function () {
                    fetching = false;
                    toggle.disabled = false;
                });
        });

        window.addEventListener('pagehide', maskKey);
    }

    function getCsrfToken() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el && el.value) return el.value;
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy') ? resolve() : reject();
            } catch (e) {
                reject(e);
            }
            document.body.removeChild(ta);
        });
    }

    function flashCopied(btn, failed) {
        var icon = btn.querySelector('i');
        var origClass = icon ? icon.className : '';
        btn.classList.add('is-copied');
        if (icon) {
            icon.className = failed ? 'fas fa-xmark' : 'fas fa-check';
        }
        setTimeout(function () {
            btn.classList.remove('is-copied');
            if (icon) icon.className = origClass;
        }, 1600);
    }
})();
