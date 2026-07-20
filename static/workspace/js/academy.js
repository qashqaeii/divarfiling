/**
 * Academy — video progress, mission steps, contextual dismiss, playlist drawer
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

        function sendProgress(force, markComplete) {
            const pos = Math.floor(video.currentTime || 0);
            if (!force && !markComplete && pos - lastSent < 5) return;
            lastSent = pos;
            const payload = { watched_seconds: pos };
            if (markComplete) {
                payload.completed = true;
            }
            postJson(url, payload).then(function (data) {
                if (data && data.completed) {
                    document.dispatchEvent(new CustomEvent('acd:video-completed', {
                        detail: { slug: slug },
                    }));
                }
            }).catch(function () {});
        }

        video.addEventListener('timeupdate', function () { sendProgress(false, false); });
        video.addEventListener('pause', function () { sendProgress(true, false); });
        video.addEventListener('ended', function () { sendProgress(true, true); });
    }

    function initPlayers() {
        document.querySelectorAll('[data-acd-video-slug]').forEach(bindVideoProgress);
    }

    function initPlaylist() {
        const toggle = document.querySelector('[data-acd-playlist-toggle]');
        const playlist = document.getElementById('acdPlaylist');
        if (!toggle || !playlist) return;

        const isDesktop = function () { return window.matchMedia('(min-width: 960px)').matches; };

        function setOpen(open) {
            playlist.classList.toggle('is-open', open);
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        }

        toggle.addEventListener('click', function () {
            setOpen(!playlist.classList.contains('is-open'));
        });

        if (playlist.querySelector('.acd-playlist-item.is-active')) {
            setOpen(true);
        }

        window.addEventListener('resize', function () {
            if (isDesktop()) {
                playlist.classList.add('is-open');
                toggle.setAttribute('aria-expanded', 'true');
            }
        });

        if (isDesktop()) {
            playlist.classList.add('is-open');
            toggle.setAttribute('aria-expanded', 'true');
        }
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
            if (!active) {
                panel.querySelectorAll('video').forEach(function (v) { v.pause(); });
            }
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
                const step = parseInt(btn.getAttribute('data-acd-step'), 10);
                showStep(step);
                cfg.currentStep = step;
                pollMission();
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

        function refreshMissionUI(data) {
            if (!data || !data.ok) return;
            if (data.completed) {
                window.location.href = '/workspace/academy/mission/?badge=1';
                return;
            }

            const nextBtn = document.querySelector('[data-acd-step-next]');
            let activeStepData = null;

            (data.steps || []).forEach(function (step) {
                updateMissionStepUI(step, cfg.currentStep);
                if (step.order === cfg.currentStep) {
                    activeStepData = step;
                }
            });

            if (nextBtn && activeStepData) {
                nextBtn.disabled = !canAdvanceStep(activeStepData);
            }
        }

        function pollMission() {
            fetch(cfg.missionPollUrl, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(refreshMissionUI);
        }

        document.addEventListener('acd:video-completed', function () {
            pollMission();
        });

        const nextBtn = document.querySelector('[data-acd-step-next]');
        const prevBtn = document.querySelector('[data-acd-step-prev]');
        if (nextBtn) {
            nextBtn.addEventListener('click', function () {
                const target = cfg.currentStep + 1;
                if (target > cfg.totalSteps) return;
                showStep(target);
                cfg.currentStep = target;
                nextBtn.disabled = true;
                document.querySelectorAll('[data-acd-step]').forEach(function (btn) {
                    const step = parseInt(btn.getAttribute('data-acd-step'), 10);
                    btn.classList.toggle('is-current', step === cfg.currentStep);
                    btn.setAttribute('aria-current', step === cfg.currentStep ? 'step' : 'false');
                });
            });
        }
        if (prevBtn) {
            prevBtn.addEventListener('click', function () {
                const target = Math.max(1, cfg.currentStep - 1);
                showStep(target);
                cfg.currentStep = target;
                pollMission();
            });
        }

        setInterval(pollMission, 15000);

        pollMission();
        initBadgeModal();
    }

    function updateMissionStepUI(step, visibleStep) {
        const panel = document.querySelector('[data-acd-step-panel="' + step.order + '"]');
        if (!panel) return;

        const videoDone = step.state === 'video_done' || step.state === 'done';
        const videoCheck = panel.querySelector('[data-check="video"]');
        if (videoCheck) {
            videoCheck.classList.toggle('is-done', videoDone);
        }

        if (step.is_done) {
            panel.querySelectorAll('.acd-mission-check').forEach(function (c) {
                c.classList.add('is-done');
            });
        }

        const statusEl = panel.querySelector('[data-acd-step-status="' + step.order + '"]');
        if (statusEl && !step.is_done) {
            if (step.state === 'video_done') {
                statusEl.textContent = 'عمل را انجام دهید یا دکمه تأیید را بزنید';
            }
        }

        const confirmBtn = panel.querySelector('[data-acd-confirm-step="' + step.order + '"]');
        if (confirmBtn && step.state === 'video_done') {
            confirmBtn.disabled = false;
        }

        const stepperBtn = document.querySelector('[data-acd-step="' + step.order + '"]');
        if (stepperBtn) {
            stepperBtn.classList.toggle('is-done', step.is_done);
            stepperBtn.classList.toggle('is-current', step.order === visibleStep);
        }
    }

    function canAdvanceStep(step) {
        if (step.is_done) return true;
        if (step.state === 'video_done' && step.confirm_type === 'video') return true;
        return false;
    }

    function initBadgeModal() {
        const modal = document.getElementById('acdBadgeModal');
        if (!modal || modal.hidden) return;

        document.body.style.overflow = 'hidden';

        document.querySelectorAll('[data-acd-close-badge]').forEach(function (el) {
            el.addEventListener('click', function () {
                modal.hidden = true;
                document.body.style.overflow = '';
            });
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.hidden) {
                modal.hidden = true;
                document.body.style.overflow = '';
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initPlayers();
        initPlaylist();
        initContextual();
        initMission();
        if (!window.acdMissionConfig) {
            initBadgeModal();
        }
    });
})();
