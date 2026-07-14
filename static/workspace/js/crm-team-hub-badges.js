/**
 * همگام‌سازی badge ناوبری آژانس (پیام + اطلاعیه)
 */
(function () {
    'use strict';

    function formatBadgeCount(n) {
        const count = Number(n) || 0;
        if (count <= 0) return '';
        return count > 99 ? '99+' : String(count);
    }

    const hubRoot = document.querySelector('[data-crm-team]');
    const state = {
        messages: Number(hubRoot?.dataset.hubMessagesUnread) || 0,
        announcements: Number(hubRoot?.dataset.hubAnnouncementsUnread) || 0,
    };

    function syncNav() {
        const link = document.querySelector('[data-nav-team-badge]');
        if (!link) return;
        const total = state.messages + state.announcements;
        const label = formatBadgeCount(total);
        let hubBadge = link.querySelector('[data-nav-team-hub-badge]');
        if (!label) {
            if (hubBadge) hubBadge.hidden = true;
            return;
        }
        if (!hubBadge) {
            hubBadge = document.createElement('span');
            hubBadge.className = 'ws-nav-badge';
            hubBadge.dataset.navTeamHubBadge = '';
            link.appendChild(hubBadge);
        }
        hubBadge.textContent = label;
        hubBadge.hidden = false;
    }

    function updateTabBadge(selector, count) {
        const badge = document.querySelector(selector);
        if (!badge) return;
        const label = formatBadgeCount(count);
        if (!label) {
            badge.hidden = true;
            badge.textContent = '0';
            return;
        }
        badge.textContent = label;
        badge.hidden = false;
    }

    window.crmTeamHubUnread = {
        setMessages(n) {
            state.messages = Number(n) || 0;
            updateTabBadge('[data-team-messages-badge]', state.messages);
            syncNav();
        },
        setAnnouncements(n) {
            state.announcements = Number(n) || 0;
            updateTabBadge('[data-team-announcements-badge]', state.announcements);
            syncNav();
        },
        syncNav,
    };

    syncNav();
})();
