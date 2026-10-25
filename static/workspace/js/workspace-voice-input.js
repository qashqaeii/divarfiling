(function (global) {
    'use strict';

    /**
     * Workspace voice auto-enhancement — wraps eligible fields once, then initCRMFieldVoice.
     * Engine: CrmSmartCommandVoice (crm-smart-command-voice.js).
     */
    const ENHANCED_ATTR = 'data-ws-voice-enhanced';

    const VOICE_FIELD_NAMES = new Set([
        'title', 'name', 'subject', 'description', 'notes', 'note', 'details', 'content',
        'body', 'message', 'comment', 'summary', 'reason', 'result', 'address', 'district',
        'neighborhood', 'amenities_extra', 'owner_name', 'tenant_name', 'tags', 'job',
        'company_name', 'transition_note', 'transition_note_progress', 'lost_reason_other',
        'payout_notes', 'next_action_note', 'reject_reason', 'reason_text',
        'problem', 'why_important', 'agency_address', 'share_message',
    ]);

    const EXCLUDED_NAMES = new Set([
        'q', 'search', 'query', 'phone', 'mobile', 'tel', 'email', 'url', 'link',
        'username', 'password', 'slug', 'token', 'secret', 'national_id', 'postal_code',
        'zip', 'code', 'otp', 'latitude', 'longitude', 'agency_latitude', 'agency_longitude',
        'agency_landline', 'agency_landline_alt', 'agency_website', 'agency_slug',
        'area', 'area_min', 'area_max', 'price', 'price_min', 'price_max', 'rooms',
        'year_min', 'year_max', 'age_max', 'min_price', 'max_price', 'value',
        'buyer_commission_amount', 'seller_commission_amount', 'deal_costs', 'received_amount',
        'contract_amount', 'contract_number', 'deposit', 'rent', 'monthly_rent', 'sale_price',
        'trigger_days', 'action_reminder_days', 'duration_minutes', 'visit_date', 'due_at',
        'next_follow_up', 'next_action_at', 'at', 'event_type', 'agency_member_q', 'region',
        'agency_city', 'kabinet', 'zonkan', 'action_reminder_title', 'trigger_statuses',
        'category', 'channel', 'doc_type', 'stage', 'customer_id', 'property_id',
    ]);

    const EXCLUDED_SELECTOR =
        '.crm-nl-command, [data-sc="input"], .crm-tpl-copy-src, #crmMsgPreview, #aiCrmPreview, '
        + '.agency-filter-bar, .crm-files-adv-filters, .mk-filter-field, .crm-list-search, '
        + '.crm-bulk-dock, [role="searchbox"], .ct-wizard-picker-search, '
        + '#crmTemplateForm [name="name"], #crmRuleForm [name="name"], '
        + '[data-voice-input-scope="off"], .crm-contact-channels, [name^="contact_social_"]';

    const INPUT_SELECTOR =
        'textarea:not([readonly]):not([aria-hidden="true"]), input[type="text"]:not([readonly])';

    const PLACEHOLDER_VOICE_RE = /توضیح|یادداشت|شرح|متن|پیام|نتیجه|خلاصه|پاسخ|مشکل/;

    const MIC_HTML =
        '<button type="button" class="crm-field-voice__mic" data-crm-field-voice-mic'
        + ' aria-label="ورود با صدا" aria-pressed="false" title="ورود با صدا">'
        + '<i class="fas fa-microphone crm-field-voice__mic-icon" data-sc="voice-icon" aria-hidden="true"></i>'
        + '</button>';

    const STATUS_HTML =
        '<p class="crm-field-voice__status" data-crm-field-voice-status role="status" aria-live="polite" hidden></p>';

    let observerStarted = false;
    let debounceTimer = null;
    /** @type {Set<Element>} */
    const pendingRoots = new Set();

    function fieldName(el) {
        const n = (el.getAttribute('name') || '').trim();
        if (n) return n.toLowerCase();
        return (el.id || '').trim().toLowerCase();
    }

    function isAlreadyEnhanced(el) {
        return el.getAttribute(ENHANCED_ATTR) === '1' || !!el.closest('[data-crm-field-voice]');
    }

    function isExcludedContainer(el) {
        return !!el.closest(EXCLUDED_SELECTOR);
    }

    function isHiddenFromEnhance(el) {
        if (el.hidden || el.type === 'hidden') return true;
        if (el.getAttribute('aria-hidden') === 'true') return true;
        const hiddenAncestor = el.closest('[hidden]');
        if (hiddenAncestor && hiddenAncestor !== el) return true;
        return false;
    }

    function isExplicitVoice(el) {
        if (el.classList.contains('ws-voice-enabled')) return true;
        const attr = el.getAttribute('data-voice-input');
        if (attr === 'off') return false;
        if (attr !== null && attr !== 'off') return true;
        return false;
    }

    function nameAllowsVoice(name) {
        if (!name) return false;
        if (EXCLUDED_NAMES.has(name)) return false;
        if (VOICE_FIELD_NAMES.has(name)) return true;
        if (name.endsWith('_note') || name.endsWith('_notes')) return true;
        return false;
    }

    function shouldEnhance(el) {
        if (!el || !(el instanceof Element)) return false;
        if (isAlreadyEnhanced(el)) return false;
        if (el.disabled || el.readOnly) return false;
        if (isHiddenFromEnhance(el)) return false;
        if (isExcludedContainer(el)) return false;
        if (el.closest('.crm-nl-command')) return false;
        if (el.getAttribute('data-voice-input') === 'off' || el.classList.contains('ws-voice-disabled')) {
            return false;
        }
        if (isExplicitVoice(el)) return true;

        const name = fieldName(el);

        if (el.tagName === 'TEXTAREA') {
            if (name && EXCLUDED_NAMES.has(name)) return false;
            if (nameAllowsVoice(name)) return true;
            if (el.placeholder && PLACEHOLDER_VOICE_RE.test(el.placeholder)) return true;
            if (
                el.classList.contains('crm-textarea')
                || el.classList.contains('ws-textarea')
                || el.classList.contains('crm-act-content')
                || el.classList.contains('crm-msg-composer-field')
                || el.classList.contains('agency-space-publish-note__input')
            ) {
                return true;
            }
            return false;
        }

        if (el.tagName === 'INPUT' && (el.type === 'text' || !el.type)) {
            if (el.classList.contains('crm-jalali-datetime')) return false;
            if (el.dataset.money || el.dataset.jdp) return false;
            const inputmode = (el.getAttribute('inputmode') || '').toLowerCase();
            if (inputmode === 'numeric' || inputmode === 'decimal' || inputmode === 'tel') return false;
            if (el.dataset.zonkanName !== undefined || el.dataset.kabinetName !== undefined) return false;
            if (el.id === 'crmZonkanName' || el.id === 'crmKabinetName') return false;
            if (el.classList.contains('crm-stages-input')) return false;
            if (name && EXCLUDED_NAMES.has(name)) return false;
            if (nameAllowsVoice(name)) return true;
            if (el.classList.contains('crm-stages-desc')) return true;
            if (el.dataset.propDealQuickName !== undefined) return true;
            if (el.id === 'crmZonkanDesc' || el.id === 'crmKabinetDesc') return true;
            if (el.dataset.zonkanDesc !== undefined || el.dataset.kabinetDesc !== undefined) return true;
            if (el.getAttribute('data-prop-deal-title') === '1') return true;
            if (el.placeholder && PLACEHOLDER_VOICE_RE.test(el.placeholder)) return true;
        }
        return false;
    }

    function wrapInput(el) {
        if (!shouldEnhance(el)) return false;

        const wrap = document.createElement('div');
        wrap.className = 'crm-field-voice';
        wrap.setAttribute('data-crm-field-voice', '');

        const inner = document.createElement('div');
        inner.className = 'crm-field-voice__wrap';

        const parent = el.parentNode;
        if (!parent) return false;

        parent.insertBefore(wrap, el);
        inner.appendChild(el);
        inner.insertAdjacentHTML('beforeend', MIC_HTML);
        wrap.appendChild(inner);
        wrap.insertAdjacentHTML('beforeend', STATUS_HTML);
        el.setAttribute(ENHANCED_ATTR, '1');
        return true;
    }

    function collectCandidates(root) {
        const out = [];
        if (!root || root.nodeType !== 1) return out;
        if (root.matches && root.matches(INPUT_SELECTOR)) out.push(root);
        if (typeof root.querySelectorAll === 'function') {
            root.querySelectorAll(INPUT_SELECTOR).forEach(function (el) {
                out.push(el);
            });
        }
        return out;
    }

    function enhanceWorkspaceVoiceInputs(root) {
        const scope = root && root.nodeType === 1 ? root : document;
        let wrapped = false;
        collectCandidates(scope).forEach(function (el) {
            if (wrapInput(el)) wrapped = true;
        });
        if (wrapped || scope.querySelector('[data-crm-field-voice]')) {
            if (typeof global.initCRMFieldVoice === 'function') {
                global.initCRMFieldVoice(scope);
            }
        }
    }

    function flushPendingRoots() {
        if (!pendingRoots.size) return;
        const roots = Array.from(pendingRoots);
        pendingRoots.clear();
        roots.forEach(function (root) {
            enhanceWorkspaceVoiceInputs(root);
        });
    }

    function scheduleEnhanceFromNodes(nodes) {
        for (let i = 0; i < nodes.length; i += 1) {
            const node = nodes[i];
            if (node.nodeType !== 1) continue;
            pendingRoots.add(node);
        }
        if (!pendingRoots.size) return;
        if (debounceTimer) global.clearTimeout(debounceTimer);
        debounceTimer = global.setTimeout(function () {
            debounceTimer = null;
            flushPendingRoots();
        }, 60);
    }

    function hookWSModal() {
        const modalApi = global.WSModal;
        if (!modalApi || modalApi.__wsVoiceHooked) return;
        const openOrig = modalApi.open.bind(modalApi);
        const closeOrig = modalApi.close.bind(modalApi);
        modalApi.open = function (id) {
            openOrig(id);
            const modal = typeof id === 'string' ? document.getElementById(id) : id;
            if (modal) enhanceWorkspaceVoiceInputs(modal);
        };
        modalApi.close = function (modal) {
            const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
            if (el && typeof global.stopCRMFieldVoiceIn === 'function') {
                global.stopCRMFieldVoiceIn(el);
            }
            closeOrig(modal);
        };
        modalApi.__wsVoiceHooked = true;
    }

    function startMutationObserver() {
        if (observerStarted || !global.MutationObserver || !document.body) return;
        observerStarted = true;
        const obs = new MutationObserver(function (mutations) {
            const added = [];
            const unhidden = [];
            for (let i = 0; i < mutations.length; i += 1) {
                const m = mutations[i];
                if (m.type === 'childList' && m.addedNodes.length) {
                    for (let j = 0; j < m.addedNodes.length; j += 1) {
                        added.push(m.addedNodes[j]);
                    }
                } else if (m.type === 'attributes' && m.target && m.target.nodeType === 1) {
                    const el = m.target;
                    if (m.attributeName === 'hidden' && !el.hidden) {
                        unhidden.push(el);
                    } else if (m.attributeName === 'class') {
                        const wasOpen = typeof m.oldValue === 'string' && /\bis-open\b/.test(m.oldValue);
                        if (!wasOpen && el.classList.contains('is-open')) {
                            unhidden.push(el);
                        }
                    } else if (m.attributeName === 'open' && el.tagName === 'DIALOG' && el.hasAttribute('open')) {
                        unhidden.push(el);
                    }
                }
            }
            if (added.length) scheduleEnhanceFromNodes(added);
            if (unhidden.length) scheduleEnhanceFromNodes(unhidden);
        });
        obs.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['hidden', 'class', 'open'],
            attributeOldValue: true,
        });
    }

    function bootstrap() {
        if (!document.body || document.body.dataset.wsVoiceBootstrap === '1') return;
        document.body.dataset.wsVoiceBootstrap = '1';
        hookWSModal();
        enhanceWorkspaceVoiceInputs(document);
        startMutationObserver();
    }

    global.enhanceWorkspaceVoiceInputs = enhanceWorkspaceVoiceInputs;
    global.initWorkspaceVoiceInput = enhanceWorkspaceVoiceInputs;
    global.__wsVoiceShouldEnhance = shouldEnhance;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootstrap);
    } else {
        bootstrap();
    }
})(typeof window !== 'undefined' ? window : globalThis);
