(function () {
    'use strict';

    var tabs = document.querySelectorAll('.arc-tab');
    var panels = document.querySelectorAll('.arc-panel');

    function showPanel(name) {
        tabs.forEach(function (tab) {
            tab.classList.toggle('is-active', tab.getAttribute('data-tab') === name);
        });
        panels.forEach(function (panel) {
            var active = panel.getAttribute('data-panel') === name;
            panel.classList.toggle('is-active', active);
            panel.hidden = !active;
        });
    }

    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            showPanel(tab.getAttribute('data-tab'));
        });
    });

    if (window.location.hash === '#arc-panel-explorer') {
        showPanel('explorer');
    }
})();
