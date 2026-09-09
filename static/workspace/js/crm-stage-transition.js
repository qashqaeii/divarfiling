/**
 * CRM Stage Transition — منطق یکپارچه تغییر مرحله (Kanban + Deal Detail)
 */
(function (global) {
    'use strict';

    var config = {
        lostStage: 'از دست رفته',
        wonStage: 'بسته‌شده',
        contractStage: 'قرارداد',
        stages: [],
    };

    var toastEl;
    var toastTimer;

    function getCsrf() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function showToast(msg, isError) {
        if (!toastEl) {
            toastEl = document.createElement('div');
            toastEl.className = 'dj-toast';
            toastEl.setAttribute('role', 'alert');
            document.body.appendChild(toastEl);
        }
        toastEl.textContent = msg;
        toastEl.className = 'dj-toast' + (isError ? ' dj-toast--error' : ' dj-toast--ok');
        toastEl.classList.add('is-visible');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { toastEl.classList.remove('is-visible'); }, 3200);
    }

    function stageIndex(name) {
        return config.stages.indexOf(name);
    }

    function isContractStage(stage) {
        if (!stage) return false;
        if (stage === config.contractStage) return true;
        return stage.indexOf('قرارداد') >= 0 && stage.indexOf('پیش') < 0;
    }

    function isProgressTarget(stage) {
        if (!stage) return false;
        var keys = ['پیشنهاد', 'مذاکره', 'پیش\u200cقرارداد', 'پیش‌قرارداد'];
        return keys.some(function (k) { return stage.indexOf(k) >= 0; });
    }

    function getTransitionType(fromStage, toStage, meta) {
        if (!toStage || toStage === fromStage) return 'none';
        if (toStage === config.lostStage) return 'lost';
        if (toStage === config.wonStage) return 'won';
        if (isContractStage(toStage) && !(meta && meta.contractCount > 0)) return 'contract';
        var fromIdx = stageIndex(fromStage);
        var toIdx = stageIndex(toStage);
        if (fromIdx >= 0 && toIdx > fromIdx && isProgressTarget(toStage)) return 'progress';
        return 'none';
    }

    function extractMetaFromCard(card) {
        if (!card) return {};
        return {
            customer: card.dataset.customer || '',
            property: card.dataset.property || '',
            value: card.dataset.value || '',
            valueLabel: card.dataset.valueLabel || '',
            contractCount: parseInt(card.dataset.contractCount || '0', 10) || 0,
            hasFinalized: card.dataset.hasFinalized === '1',
            createContractUrl: card.dataset.createContractUrl || '',
        };
    }

    function resetDialog(form) {
        form.reset();
        var lostHidden = document.getElementById('djTransitionLostReason');
        if (lostHidden) lostHidden.value = '';
        form.querySelectorAll('.dj-lost-chip input').forEach(function (inp) { inp.checked = false; });
    }

    function configureDialog(type, fromStage, toStage, meta) {
        var dialog = document.getElementById('djStageTransition');
        var desc = document.getElementById('djTransitionDesc');
        var wonWrap = document.getElementById('djTransitionWonWrap');
        var lostWrap = document.getElementById('djTransitionLostWrap');
        var contractWrap = document.getElementById('djTransitionContractWrap');
        var noteWrap = document.getElementById('djTransitionNoteWrap');
        var nextWrap = document.getElementById('djTransitionNextWrap');
        var submitBtn = document.getElementById('djTransitionSubmit');
        var title = document.getElementById('djTransitionTitle');
        if (!dialog || !desc) return;

        wonWrap.hidden = type !== 'won';
        lostWrap.hidden = type !== 'lost';
        contractWrap.hidden = type !== 'contract';
        noteWrap.hidden = type === 'won' || type === 'lost' || type === 'contract';
        nextWrap.hidden = type === 'won' || type === 'lost';
        if (type === 'contract') nextWrap.hidden = true;

        desc.textContent = 'انتقال معامله از «' + fromStage + '» به «' + toStage + '»';

        if (type === 'won') {
            title.textContent = 'بستن معامله';
            submitBtn.textContent = 'بستن معامله';
            document.getElementById('djTransCustomer').textContent = meta.customer || '—';
            document.getElementById('djTransProperty').textContent = meta.property || '—';
            document.getElementById('djTransValue').textContent = meta.valueLabel || meta.value || '—';
            var contractRow = document.getElementById('djTransContractRow');
            var wonWarn = document.getElementById('djTransitionWonWarn');
            if (meta.hasFinalized) {
                contractRow.hidden = false;
                document.getElementById('djTransContract').textContent = 'قرارداد نهایی‌شده';
                wonWarn.hidden = true;
            } else if (meta.contractCount > 0) {
                contractRow.hidden = false;
                document.getElementById('djTransContract').textContent = meta.contractCount + ' قرارداد';
                wonWarn.hidden = true;
            } else {
                contractRow.hidden = true;
                wonWarn.hidden = false;
            }
        } else if (type === 'lost') {
            title.textContent = 'از دست رفتن معامله';
            submitBtn.textContent = 'ثبت و انتقال';
        } else if (type === 'contract') {
            title.textContent = 'انتقال به مرحله قرارداد';
            submitBtn.textContent = 'تأیید انتقال';
            var createLink = document.getElementById('djTransitionCreateContract');
            if (createLink && meta.createContractUrl) createLink.href = meta.createContractUrl;
        } else if (type === 'progress') {
            title.textContent = 'انتقال به «' + toStage + '»';
            submitBtn.textContent = 'تأیید انتقال';
        } else {
            title.textContent = 'انتقال مرحله';
            submitBtn.textContent = 'تأیید انتقال';
        }
    }

    function collectLostReason(form) {
        var choice = form.querySelector('input[name="lost_reason_choice"]:checked');
        if (!choice) return '';
        if (choice.value === 'سایر') {
            return (form.querySelector('[name="lost_reason_other"]') || {}).value || '';
        }
        return choice.value;
    }

    function bindLostChips(form) {
        var otherWrap = document.getElementById('djTransitionLostOther');
        var hidden = document.getElementById('djTransitionLostReason');
        form.querySelectorAll('.dj-lost-chip input').forEach(function (inp) {
            inp.addEventListener('change', function () {
                if (otherWrap) otherWrap.hidden = inp.value !== 'سایر';
                if (hidden) hidden.value = inp.value === 'سایر' ? '' : inp.value;
            });
        });
    }

    function postStageChange(stageUrl, body) {
        return fetch(stageUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(body),
        }).then(function (res) {
            return res.json().then(function (data) {
                if (!res.ok || !data.ok) throw new Error(data.error || 'تغییر مرحله انجام نشد.');
                return data;
            });
        });
    }

    function postNextAction(type, at, note) {
        if (!type || !global.crmDealNextActionUrl) return Promise.resolve();
        return fetch(global.crmDealNextActionUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ type: type, at: at || '', note: note || '' }),
        });
    }

    function postFollowupNote(note) {
        if (!note || !global.crmDealFollowUpUrl) return Promise.resolve();
        return fetch(global.crmDealFollowUpUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ type: 'یادداشت', note: note }),
        });
    }

    function showDialog(fromStage, toStage, meta) {
        return new Promise(function (resolve) {
            var dialog = document.getElementById('djStageTransition');
            var form = document.getElementById('djTransitionForm');
            if (!dialog || !form) {
                resolve(null);
                return;
            }
            var type = getTransitionType(fromStage, toStage, meta);
            resetDialog(form);
            configureDialog(type, fromStage, toStage, meta);
            dialog.dataset.pendingType = type;
            dialog.dataset.pendingTo = toStage;
            dialog.dataset.pendingFrom = fromStage;

            function cleanup() {
                form.removeEventListener('submit', onSubmit);
                dialog.querySelectorAll('[data-transition-cancel]').forEach(function (el) {
                    el.removeEventListener('click', onCancel);
                });
                var skipBtn = dialog.querySelector('[data-transition-skip-contract]');
                if (skipBtn) skipBtn.removeEventListener('click', onSkipContract);
            }

            function onCancel() {
                cleanup();
                dialog.close();
                resolve(null);
            }

            function onSkipContract() {
                cleanup();
                dialog.close();
                resolve({ stage: toStage, skipContractPrompt: true });
            }

            function onSubmit(e) {
                e.preventDefault();
                var t = dialog.dataset.pendingType;
                var lostReason = '';
                if (t === 'lost') {
                    var choice = form.querySelector('input[name="lost_reason_choice"]:checked');
                    if (!choice) {
                        showToast('دلیل از دست رفتن را انتخاب کنید.', true);
                        return;
                    }
                    if (choice.value === 'سایر') {
                        lostReason = ((form.querySelector('[name="lost_reason_other"]') || {}).value || '').trim();
                    } else {
                        lostReason = choice.value;
                    }
                    if (!lostReason) {
                        showToast('دلیل را بنویسید.', true);
                        return;
                    }
                }
                var note = '';
                if (t === 'won') {
                    note = (form.querySelector('[name="transition_note"]') || {}).value || '';
                } else if (t === 'progress') {
                    note = (form.querySelector('[name="transition_note_progress"]') || {}).value || '';
                }
                var nextType = (form.querySelector('[name="next_action_type"]') || {}).value || '';
                var nextAt = (form.querySelector('[name="next_action_at"]') || {}).value || '';
                var nextNote = (form.querySelector('[name="next_action_note"]') || {}).value || '';
                cleanup();
                dialog.close();
                resolve({
                    stage: toStage,
                    lost_reason: lostReason,
                    note: note.trim(),
                    next_action_type: nextType,
                    next_action_at: nextAt,
                    next_action_note: nextNote,
                });
            }

            form.addEventListener('submit', onSubmit);
            dialog.querySelectorAll('[data-transition-cancel]').forEach(function (el) {
                el.addEventListener('click', onCancel);
            });
            var skipBtn = dialog.querySelector('[data-transition-skip-contract]');
            if (skipBtn && type === 'contract') {
                skipBtn.addEventListener('click', onSkipContract);
            }
            dialog.showModal();
        });
    }

    function applyStageChange(stageUrl, payload) {
        var body = { stage: payload.stage, lost_reason: payload.lost_reason || '' };
        return postStageChange(stageUrl, body).then(function () {
            var chain = Promise.resolve();
            if (payload.next_action_type) {
                chain = chain.then(function () {
                    return postNextAction(payload.next_action_type, payload.next_action_at, payload.next_action_note);
                });
            }
            if (payload.note) {
                chain = chain.then(function () { return postFollowupNote(payload.note); });
            }
            return chain;
        });
    }

    function requestTransition(opts) {
        var fromStage = opts.fromStage || '';
        var toStage = opts.toStage || '';
        var meta = opts.meta || {};
        var type = getTransitionType(fromStage, toStage, meta);
        if (type === 'none') {
            return applyStageChange(opts.stageUrl, { stage: toStage });
        }
        return showDialog(fromStage, toStage, meta).then(function (result) {
            if (!result) return Promise.reject(new Error('cancelled'));
            return applyStageChange(opts.stageUrl, result);
        });
    }

    function init(userConfig) {
        if (userConfig) {
            config.lostStage = userConfig.lostStage || config.lostStage;
            config.wonStage = userConfig.wonStage || config.wonStage;
            config.contractStage = userConfig.contractStage || config.contractStage;
            config.stages = userConfig.stages || config.stages;
        }
        var form = document.getElementById('djTransitionForm');
        if (form) bindLostChips(form);
    }

    global.CRMStageTransition = {
        init: init,
        getTransitionType: getTransitionType,
        extractMetaFromCard: extractMetaFromCard,
        requestTransition: requestTransition,
        applyStageChange: applyStageChange,
        showDialog: showDialog,
        showToast: showToast,
        getCsrf: getCsrf,
    };
})(window);
