(function () {
    'use strict';

    var list = document.getElementById('crm-files-list');
    if (!list) return;

    var sentinel = document.getElementById('crm-files-load-sentinel');
    var statusEl = document.getElementById('crm-files-load-status');
    var loading = false;

    function hasNext() {
        return list.getAttribute('data-has-next') === '1';
    }

    function getNextPage() {
        var raw = list.getAttribute('data-next-page');
        return raw ? parseInt(raw, 10) : null;
    }

    function getView() {
        return list.getAttribute('data-view') || 'grid';
    }

    function getBody() {
        return document.getElementById('crm-files-list-body') || list;
    }

    function setLoading(on) {
        loading = on;
        if (!statusEl) return;
        if (on) {
            statusEl.textContent = 'در حال بارگذاری فایل‌ها…';
            statusEl.hidden = false;
        } else {
            statusEl.hidden = true;
        }
    }

    function appendHtml(html) {
        var body = getBody();
        var view = getView();
        var trimmed = (html || '').trim();
        if (!trimmed) return;

        if (view === 'table') {
            var tmp = document.createElement('tbody');
            tmp.innerHTML = trimmed;
            while (tmp.firstChild) body.appendChild(tmp.firstChild);
            return;
        }

        var wrap = document.createElement('div');
        wrap.innerHTML = trimmed;
        var cards = wrap.querySelectorAll('.crm-files-card');
        cards.forEach(function (card) { body.appendChild(card); });
    }

    function loadMore() {
        var nextPage = getNextPage();
        if (!hasNext() || !nextPage || loading) return;

        setLoading(true);

        var params = new URLSearchParams(window.location.search);
        params.set('partial', '1');
        params.set('page', String(nextPage));

        fetch(window.location.pathname + '?' + params.toString(), {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        })
            .then(function (res) {
                if (!res.ok) throw new Error('load failed');
                return res.json();
            })
            .then(function (data) {
                if (data.html) appendHtml(data.html);

                if (data.has_next && data.next_page) {
                    list.setAttribute('data-has-next', '1');
                    list.setAttribute('data-next-page', String(data.next_page));
                } else {
                    list.setAttribute('data-has-next', '0');
                    list.removeAttribute('data-next-page');
                    if (sentinel) sentinel.hidden = true;
                }
            })
            .catch(function () {
                if (statusEl) {
                    statusEl.textContent = 'بارگذاری ناموفق بود. دوباره اسکرول کنید.';
                    statusEl.hidden = false;
                }
            })
            .finally(function () { setLoading(false); });
    }

    if (sentinel && 'IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) loadMore();
            });
        }, { root: null, rootMargin: '280px 0px 280px 0px', threshold: 0 });
        observer.observe(sentinel);
    }
})();
