/**
 * Academy — video progress, mission steps, contextual dismiss
 */
(function () {
    'use strict';

    function csrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify(body || {}),
        }).then(function (r) { return r.json(); });
    }

    function trackEvent(type, meta) {
        postJson('/workspace/api/academy/events/', {
            events: [{ event_type: type, metadata: meta || {} }],
        }).catch(function () {});
    }

    function bindVideoProgress(root) {
        const slugEl = root.matches('[data-acd-video-slug]') ? root : root.querySelector('[data-acd-video-slug]');
        if (!slugEl) return;
        const slug = slugEl.getAttribute('data-acd-video-slug');
        if (!slug) return;
        const cfg = window.acdPathConfig || window.acdMissionConfig || {};
        const urlTpl = cfg.progressUrl || '/workspace/api/academy/video/__SLUG__/progress/';
        const url = urlTpl.replace('__SLUG__', slug);
        const video = slugEl.querySelector('video') || root.querySelector('video');
        if (!video) return;
        let lastSent = 0;
        let started = false;

        video.addEventListener('play', function () {
            if (!started) {
                started = true;
                trackEvent('academy_video_started', { video_slug: slug });
            }
        });

        function sendProgress(force) {
            const pos = Math.floor(video.currentTime || 0);
            if (!force && pos - lastSent < 5) return;
            lastSent = pos;
            const dur = video.duration || 0;
            const completed = dur > 0 && pos >= dur * 0.9;
            postJson(url, { watched_seconds: pos, completed: completed }).then(function (data) {
                if (data && data.completed) {
                    document.dispatchEvent(new CustomEvent('acd:video-completed', {
                        detail: { slug: slug },
                    }));
                }
            }).catch(function () {});
        }

        video.addEventListener('timeupdate', function () { sendProgress(false); });
        video.addEventListener('pause', function () { sendProgress(true); });
        video.addEventListener('ended', function () { sendProgress(true); });
    }

    function initPlayers() {
        document.querySelectorAll('[data-acd-video-slug]').forEach(bindVideoProgress);
    }

    function initContextual() {
        document.querySelectorAll('[data-acd-dismiss-contextual]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const key = btn.getAttribute('data-acd-dismiss-contextual');
                postJson('/workspace/api/academy/contextual/dismiss/', { key: key }).then(function () {
                    const wrap = btn.closest('[data-acd-contextual]');
                    if (wrap) wrap.remove();
                });
            });
        });
        document.querySelectorAll('[data-acd-contextual]').forEach(function (el) {
            trackEvent('academy_contextual_shown', { page_key: el.getAttribute('data-acd-contextual') });
        });
        document.querySelectorAll('[data-acd-cta]').forEach(function (el) {
            el.addEventListener('click', function () {
                trackEvent('academy_cta_clicked', { url: el.getAttribute('href') });
            });
        });
    }

    function showStep(n) {
        document.querySelectorAll('[data-acd-step-panel]').forEach(function (panel) {
            const step = parseInt(panel.getAttribute('data-acd-step-panel'), 10);
            const active = step === n;
            panel.classList.toggle('is-active', active);
            panel.hidden = !active;
        });
        document.querySelectorAll('[data-acd-step]').forEach(function (btn) {
            const step = parseInt(btn.getAttribute('data-acd-step'), 10);
            btn.classList.toggle('is-current', step === n);
            btn.setAttribute('aria-current', step === n ? 'step' : 'false');
        });
    }

    function initMission() {
        const cfg = window.acdMissionConfig;
        if (!cfg) return;

        document.querySelectorAll('[data-acd-step]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                showStep(parseInt(btn.getAttribute('data-acd-step'), 10));
            });
        });

        document.querySelectorAll('[data-acd-confirm-step]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const step = btn.getAttribute('data-acd-confirm-step');
                const url = cfg.stepCompleteUrl + step + '/complete/';
                btn.disabled = true;
                postJson(url, {}).then(function (data) {
                    if (data.ok) {
                        if (data.completed) {
                            window.location.href = '/workspace/academy/mission/?badge=1';
                            return;
                        }
                        pollMission();
                    } else {
                        btn.disabled = false;
                    }
                }).catch(function () { btn.disabled = false; });
            });
        });

        function pollMission() {
            fetch(cfg.missionPollUrl, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!data.ok) return;
                    if (data.completed) {
                        window.location.href = '/workspace/academy/mission/?badge=1';
                        return;
                    }
                    (data.steps || []).forEach(function (step) {
                        if (step.is_done) {
                            const panel = document.querySelector('[data-acd-step-panel="' + step.order + '"]');
                            if (panel) {
                                panel.querySelectorAll('.acd-mission-check').forEach(function (c) {
                                    c.classList.add('is-done');
                                });
                            }
                        }
                        if (step.is_current) {
                            showStep(step.order);
                            cfg.currentStep = step.order;
                            const nextBtn = document.querySelector('[data-acd-step-next]');
                            if (nextBtn && step.is_done) nextBtn.disabled = false;
                        }
                    });
                });
        }

        document.addEventListener('acd:video-completed', function () {
            pollMission();
        });

        const nextBtn = document.querySelector('[data-acd-step-next]');
        const prevBtn = document.querySelector('[data-acd-step-prev]');
        if (nextBtn) {
            nextBtn.addEventListener('click', function () {
                showStep(cfg.currentStep + 1);
                cfg.currentStep += 1;
                nextBtn.disabled = true;
            });
        }
        if (prevBtn) {
            prevBtn.addEventListener('click', function () {
                showStep(Math.max(1, cfg.currentStep - 1));
                cfg.currentStep = Math.max(1, cfg.currentStep - 1);
            });
        }

        setInterval(pollMission, 8000);

        document.querySelectorAll('[data-acd-close-badge]').forEach(function (el) {
            el.addEventListener('click', function () {
                const modal = document.getElementById('acdBadgeModal');
                if (modal) modal.hidden = true;
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initPlayers();
        initContextual();
        initMission();
    });
})();
