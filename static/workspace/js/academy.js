/**
 * Academy — video progress, playlist drawer, search, contextual dismiss
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

    function prefersReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function bindVideoResume(slugEl, video) {
        const resumeRaw = slugEl.getAttribute('data-acd-resume-seconds');
        const resumeAt = parseInt(resumeRaw || '0', 10);
        if (!resumeAt || resumeAt <= 0) return;

        const bar = slugEl.parentElement
            ? slugEl.parentElement.querySelector('[data-acd-resume-bar]')
            : document.querySelector('[data-acd-resume-bar]');
        const maxDur = parseInt(slugEl.getAttribute('data-acd-duration') || '0', 10);

        function clampPos(sec) {
            let pos = Math.max(0, sec);
            if (maxDur > 0) pos = Math.min(pos, maxDur);
            return pos;
        }

        function showBar() {
            if (bar) bar.hidden = false;
        }

        function applyResume() {
            const target = clampPos(resumeAt);
            if (target > 0 && video.duration && video.currentTime < 1) {
                try {
                    video.currentTime = Math.min(target, Math.max(video.duration - 0.5, 0));
                } catch (e) { /* ignore */ }
            }
        }

        video.addEventListener('loadedmetadata', function () {
            showBar();
        });

        if (bar) {
            const applyBtn = bar.querySelector('[data-acd-resume-apply]');
            const dismissBtn = bar.querySelector('[data-acd-resume-dismiss]');
            if (applyBtn) {
                applyBtn.addEventListener('click', function () {
                    applyResume();
                    bar.hidden = true;
                });
            }
            if (dismissBtn) {
                dismissBtn.addEventListener('click', function () {
                    try { video.currentTime = 0; } catch (e) { /* ignore */ }
                    bar.hidden = true;
                });
            }
        }
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
        bindVideoResume(slugEl, video);
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
        const isMobile = function () { return window.matchMedia('(max-width: 767px)').matches; };

        function scrollActiveLesson() {
            if (!isMobile() || !playlist.classList.contains('is-open')) return;
            const active = playlist.querySelector('.acd-playlist-item.is-active');
            const inner = playlist.querySelector('.acd-playlist-body-inner');
            if (!active || !inner) return;
            const innerRect = inner.getBoundingClientRect();
            const itemRect = active.getBoundingClientRect();
            if (itemRect.top < innerRect.top) {
                inner.scrollTop -= (innerRect.top - itemRect.top);
            } else if (itemRect.bottom > innerRect.bottom) {
                inner.scrollTop += (itemRect.bottom - innerRect.bottom);
            }
        }

        function setOpen(open) {
            playlist.classList.toggle('is-open', open);
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (open) {
                window.requestAnimationFrame(scrollActiveLesson);
            }
        }

        toggle.addEventListener('click', function () {
            setOpen(!playlist.classList.contains('is-open'));
        });

        const hasActive = playlist.querySelector('.acd-playlist-item.is-active');
        if (hasActive) {
            setOpen(isDesktop());
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

    function dismissContextualEl(el) {
        if (!el || el.classList.contains('is-leaving')) return;
        el.classList.add('is-leaving');
        window.setTimeout(function () {
            const shell = el.closest('.acd-contextual-shell');
            if (shell) shell.remove();
            else el.remove();
        }, 220);
    }

    function resetContextualModalVideo(modal) {
        if (!modal) return;
        modal.querySelectorAll('video').forEach(function (video) {
            try { video.pause(); } catch (e) { /* ignore */ }
            try { video.currentTime = 0; } catch (e) { /* ignore */ }
            video.removeAttribute('controls');
            const frame = video.closest('.mk-vid-frame');
            if (frame) {
                frame.classList.remove('is-playing', 'is-ended');
            }
        });
    }

    function initContextualModal(modal) {
        if (!modal || modal.dataset.acdContextualModalBound === '1') return;
        modal.dataset.acdContextualModalBound = '1';
        modal.querySelectorAll('[data-acd-contextual-modal-close]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                resetContextualModalVideo(modal);
            });
        });
        bindVideoProgress(modal);
    }

    function initContextual() {
        document.querySelectorAll('[data-acd-dismiss-contextual]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const key = btn.getAttribute('data-acd-dismiss-contextual');
                const wrap = btn.closest('[data-acd-contextual]');
                postJson('/workspace/api/academy/contextual/dismiss/', { key: key }).then(function () {
                    dismissContextualEl(wrap);
                });
            });
        });
        document.querySelectorAll('[data-acd-contextual]').forEach(function (el) {
            trackEvent('academy_contextual_shown', { page_key: el.getAttribute('data-acd-contextual') });
        });
        document.querySelectorAll('[data-acd-cta]').forEach(function (el) {
            el.addEventListener('click', function () {
                trackEvent('academy_cta_clicked', {
                    url: el.getAttribute('href') || el.getAttribute('data-modal-open') || '',
                });
            });
        });
        document.querySelectorAll('[data-acd-contextual-modal]').forEach(initContextualModal);
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') return;
            document.querySelectorAll('[data-acd-contextual-modal].is-open').forEach(resetContextualModalVideo);
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

    function normalizeFaQuery(raw) {
        return String(raw || '').trim().toLowerCase()
            .replace(/ي/g, 'ی').replace(/ك/g, 'ک');
    }

    function initAcademySearch() {
        var dataEl = document.getElementById('acdSearchData');
        var input = document.getElementById('acdSearchInput');
        var list = document.getElementById('acdSearchResults');
        var empty = document.getElementById('acdSearchEmpty');
        if (!dataEl || !input || !list) return;

        var entries = [];
        try {
            entries = JSON.parse(dataEl.textContent || '[]');
        } catch (e) {
            return;
        }

        function render(q) {
            var query = normalizeFaQuery(q);
            var matches = entries;
            if (query) {
                function scoreItem(item) {
                    var blob = normalizeFaQuery(item.searchText || item.title || '');
                    var s = 0;
                    if (blob.indexOf(query) !== -1) s += 100;
                    (item.keywords || []).forEach(function (kw) {
                        var nkw = normalizeFaQuery(kw);
                        if (query === nkw) s += 90;
                        else if (nkw.indexOf(query) !== -1 || query.indexOf(nkw) !== -1) s += 70;
                    });
                    query.split(/\s+/).forEach(function (tok) {
                        if (tok.length >= 2 && blob.indexOf(tok) !== -1) s += 12;
                    });
                    return s;
                }
                matches = entries
                    .map(function (item) { return { item: item, score: scoreItem(item) }; })
                    .filter(function (row) { return row.score > 0; })
                    .sort(function (a, b) { return b.score - a.score; })
                    .map(function (row) { return row.item; });
            }
            list.innerHTML = '';
            if (!query) {
                list.hidden = true;
                if (empty) empty.hidden = true;
                return;
            }
            if (!matches.length) {
                list.hidden = true;
                if (empty) empty.hidden = false;
                return;
            }
            if (empty) empty.hidden = true;
            list.hidden = false;
            matches.forEach(function (item) {
                var li = document.createElement('li');
                var a = document.createElement('a');
                a.href = item.url;
                a.className = 'acd-search-hit';
                var titleEl = document.createElement('strong');
                titleEl.textContent = item.title || '';
                var pathEl = document.createElement('small');
                pathEl.textContent = item.path || '';
                a.appendChild(titleEl);
                a.appendChild(pathEl);
                li.appendChild(a);
                list.appendChild(li);
            });
        }

        input.addEventListener('input', function () { render(input.value); });
        input.addEventListener('search', function () { render(input.value); });
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

    function initLessonDock() {
        const dock = document.querySelector('[data-acd-lesson-dock]');
        if (!dock) return;

        function syncDockVisibility() {
            const fs = document.fullscreenElement || document.webkitFullscreenElement;
            const hide = Boolean(fs);
            document.body.classList.toggle('acd-dock-hidden', hide);
        }

        document.addEventListener('fullscreenchange', syncDockVisibility);
        document.addEventListener('webkitfullscreenchange', syncDockVisibility);
        syncDockVisibility();
    }

    document.addEventListener('DOMContentLoaded', function () {
        initPlayers();
        initPlaylist();
        initContextual();
        initAcademySearch();
        initMission();
        initLessonDock();
        if (!window.acdMissionConfig) {
            initBadgeModal();
        }
    });
})();
