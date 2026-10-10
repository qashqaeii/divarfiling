(function () {
    'use strict';

    var timeline = document.getElementById('crm-rm-timeline');
    if (!timeline) return;

    var sentinel = document.getElementById('crm-rm-load-sentinel');
    var statusEl = document.getElementById('crm-rm-load-status');
    var loading = false;

    function csrfToken() {
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (m) return decodeURIComponent(m[1]);
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function hasNext() {
        return timeline.getAttribute('data-has-next') === '1';
    }

    function getNextPage() {
        var raw = timeline.getAttribute('data-next-page');
        return raw ? parseInt(raw, 10) : null;
    }

    function getShow() {
        return timeline.getAttribute('data-show') || 'active';
    }

    function setLoading(on) {
        loading = on;
        if (statusEl) statusEl.hidden = !on;
    }

    function updateStat(key, value) {
        document.querySelectorAll('[data-stat="' + key + '"]').forEach(function (el) {
            if (key === 'total') {
                el.textContent = value + ' یادآور';
            } else {
                el.textContent = String(value);
            }
        });

        document.querySelectorAll('[data-stat-wrap="' + key + '"]').forEach(function (el) {
            if (key === 'overdue') {
                if (value > 0) {
                    el.hidden = false;
                    if (el.classList.contains('crm-rm-mob-stat-pill--warn')) {
                        el.innerHTML = 'معوق <strong data-stat="overdue">' + value + '</strong>';
                    } else {
                        el.innerHTML = '<i class="fas fa-circle" aria-hidden="true"></i> ' + value + ' مورد نیاز به پیگیری فوری';
                    }
                } else {
                    el.hidden = true;
                }
            } else if (key === 'today' && el.hasAttribute('data-stat-wrap')) {
                if (value > 0) {
                    el.hidden = false;
                    el.textContent = value + ' امروز';
                } else {
                    el.hidden = true;
                }
            }
        });

        if (key === 'active' || key === 'done') {
            document.querySelectorAll('.crm-rm-seg-count[data-stat="' + key + '"]').forEach(function (el) {
                if (value > 0) {
                    el.textContent = String(value);
                    el.hidden = false;
                } else {
                    el.hidden = true;
                }
            });
        }
    }

    function applyStats(stats) {
        if (!stats) return;
        ['active', 'done', 'overdue', 'today'].forEach(function (k) {
            if (stats[k] !== undefined) updateStat(k, stats[k]);
        });
    }

    function removeCard(card) {
        card.style.transition = 'opacity 0.22s ease, transform 0.22s ease';
        card.style.opacity = '0';
        card.style.transform = 'translateY(-6px)';
        setTimeout(function () {
            card.remove();
            var total = parseInt(timeline.getAttribute('data-total') || '0', 10);
            if (!isNaN(total) && total > 0) {
                timeline.setAttribute('data-total', String(total - 1));
                updateStat('total', total - 1);
            }
            if (!timeline.querySelector('.crm-rm-card')) {
                timeline.hidden = true;
                if (sentinel) sentinel.hidden = true;
                var hint = document.getElementById('crm-rm-empty-hint');
                if (!hint) {
                    hint = document.createElement('p');
                    hint.id = 'crm-rm-empty-hint';
                    hint.className = 'crm-rm-load-status';
                    hint.textContent = 'یادآوری در این بخش نیست.';
                    timeline.parentNode.insertBefore(hint, timeline.nextSibling);
                }
                hint.hidden = false;
            }
        }, 220);
    }

    function updateToggleButton(btn, isDone) {
        btn.classList.toggle('is-done', isDone);
        btn.classList.toggle('is-pending', !isDone);
        btn.setAttribute('aria-label', isDone ? 'بازگردانی یادآور' : 'علامت‌گذاری به‌عنوان انجام‌شده');
        btn.title = isDone ? 'بازگردانی' : 'انجام شد';
        var icon = btn.querySelector('.crm-rm-complete-icon i');
        if (icon) {
            icon.className = 'fas fa-' + (isDone ? 'rotate-left' : 'check');
        }
        var label = btn.querySelector('.crm-rm-complete-label');
        if (label) label.textContent = isDone ? 'بازگردانی' : 'انجام شد';
        var title = btn.closest('.crm-rm-card').querySelector('.crm-rm-title');
        if (title) title.classList.toggle('is-done', isDone);
        var badge = btn.closest('.crm-rm-card').querySelector('.crm-rm-tone-badge');
        if (badge && isDone) badge.textContent = 'انجام‌شده';
    }

    function shouldRemoveCard(show, isDone) {
        if (show === 'active' && isDone) return true;
        if (show === 'done' && !isDone) return true;
        return false;
    }

    function loadMore() {
        var nextPage = getNextPage();
        if (!hasNext() || !nextPage || loading) return;

        setLoading(true);

        var show = getShow();
        var params = new URLSearchParams({ partial: '1', page: String(nextPage), show: show });

        fetch(window.location.pathname + '?' + params.toString(), {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        })
            .then(function (res) {
                if (!res.ok) throw new Error('load failed');
                return res.json();
            })
            .then(function (data) {
                if (!data.html) return;

                var wrap = document.createElement('div');
                wrap.innerHTML = data.html.trim();
                var cards = wrap.querySelectorAll('.crm-rm-card');
                cards.forEach(function (card) { timeline.appendChild(card); });

                if (data.has_next && data.next_page) {
                    timeline.setAttribute('data-has-next', '1');
                    timeline.setAttribute('data-next-page', String(data.next_page));
                } else {
                    timeline.setAttribute('data-has-next', '0');
                    timeline.removeAttribute('data-next-page');
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

    timeline.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form.classList.contains('crm-rm-check-form')) return;
        e.preventDefault();

        var btn = form.querySelector('.crm-rm-complete-btn');
        var card = form.closest('.crm-rm-card');
        if (!btn || btn.disabled) return;

        btn.disabled = true;

        fetch(form.action, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: new URLSearchParams({ csrfmiddlewaretoken: csrfToken() }).toString(),
            credentials: 'same-origin',
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok || data.ok === false) {
                        throw new Error(data.error || 'خطا در به‌روزرسانی');
                    }
                    return data;
                });
            })
            .then(function (data) {
                applyStats(data.stats);
                var show = getShow();
                if (shouldRemoveCard(show, data.is_done)) {
                    removeCard(card);
                } else {
                    updateToggleButton(btn, data.is_done);
                    btn.disabled = false;
                }
            })
            .catch(function (err) {
                btn.disabled = false;
                if (statusEl) {
                    statusEl.textContent = err.message || 'خطا در به‌روزرسانی';
                    statusEl.hidden = false;
                    setTimeout(function () { statusEl.hidden = true; }, 3000);
                }
            });
    });
})();
